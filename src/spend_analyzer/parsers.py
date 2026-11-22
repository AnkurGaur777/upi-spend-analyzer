# src/spend_analyzer/parsers.py
import hashlib
from pathlib import Path
import pandas as pd

UNIFIED_COLUMNS = ["txn_date", "narration", "amount", "direction", "balance", "source_bank", "txn_id"]

BANK_FORMATS = {
    "hdfc_like": {
        "date": "Date",
        "narration": "Narration",
        "debit": "Withdrawal Amt.",
        "credit": "Deposit Amt.",
        "balance": "Closing Balance",
        "date_fmt": "%d/%m/%y",
    },
    "icici_like": {
        "date": "Transaction Date",
        "narration": "Transaction Details",
        "debit": "Debit Amount",
        "credit": "Credit Amount",
        "balance": "Balance",
        "date_fmt": "%d-%m-%Y",
    },
}


def _num(s: pd.Series) -> pd.Series:
    """'1,234.50' -> 1234.5 ; '' -> 0.0"""
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip().replace({"": "0", "nan": "0"}),
                         errors="coerce").fillna(0.0)


def make_txn_id(row) -> str:
    key = f"{row.txn_date}|{row.narration}|{row.amount}|{row.direction}|{row.balance}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def detect_bank_format(df_or_path: str | Path | pd.DataFrame) -> str:
    """Detect bank layout from column names."""
    if isinstance(df_or_path, (str, Path)):
        sample = pd.read_csv(df_or_path, nrows=5, dtype=str)
    else:
        sample = df_or_path

    cols = set(sample.columns)
    for fmt_name, cfg in BANK_FORMATS.items():
        req = [cfg["date"], cfg["narration"], cfg["debit"], cfg["credit"], cfg["balance"]]
        if all(c in cols for c in req):
            return fmt_name
    raise ValueError(f"Unrecognized statement format. Header columns: {sorted(cols)}")


def parse_csv(
    path: str | Path,
    fmt: str | None = "auto",
    bank: str | None = None,
    source_bank: str | None = None,
) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Statement file not found: {path}")

    selected_fmt = bank or fmt
    if selected_fmt is None or selected_fmt == "auto":
        selected_fmt = detect_bank_format(path)

    if selected_fmt not in BANK_FORMATS:
        raise ValueError(
            f"Unknown bank format '{selected_fmt}'. Supported formats: {list(BANK_FORMATS.keys())}"
        )

    cfg = BANK_FORMATS[selected_fmt]
    raw = pd.read_csv(path, dtype=str)

    required_cols = [cfg["date"], cfg["narration"], cfg["debit"], cfg["credit"], cfg["balance"]]
    missing_cols = [c for c in required_cols if c not in raw.columns]
    if missing_cols:
        raise ValueError(
            f"File '{path.name}' is missing required columns for format '{selected_fmt}': {missing_cols}"
        )

    out = pd.DataFrame()
    out["txn_date"] = pd.to_datetime(raw[cfg["date"]], format=cfg["date_fmt"]).dt.date
    out["narration"] = raw[cfg["narration"]].fillna("").str.strip()
    debit, credit = _num(raw[cfg["debit"]]), _num(raw[cfg["credit"]])
    out["direction"] = (credit > 0).map({True: "credit", False: "debit"})
    out["amount"] = (credit + debit).round(2)
    out["balance"] = _num(raw[cfg["balance"]])
    out["source_bank"] = source_bank or selected_fmt
    out["txn_id"] = out.apply(make_txn_id, axis=1)
    out = out[UNIFIED_COLUMNS]
    return out.drop_duplicates("txn_id").reset_index(drop=True)
