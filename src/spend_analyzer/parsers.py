# src/spend_analyzer/parsers.py
import hashlib
import pandas as pd

UNIFIED_COLUMNS = ["txn_date", "narration", "amount", "direction", "balance", "source_bank", "txn_id"]

BANK_FORMATS = {
    "hdfc_like": {
        "date": "Date", "narration": "Narration", "debit": "Withdrawal Amt.",
        "credit": "Deposit Amt.", "balance": "Closing Balance", "date_fmt": "%d/%m/%y",
    },
    # Add more layouts here. Example for a single signed-amount layout:
    # "other_bank": {"date": "Txn Date", "narration": "Description", "amount": "Amount", ...}
}


def _num(s: pd.Series) -> pd.Series:
    """'1,234.50' -> 1234.5 ; '' -> 0.0"""
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip().replace({"": "0", "nan": "0"}),
                         errors="coerce").fillna(0.0)


def make_txn_id(row) -> str:
    key = f"{row.txn_date}|{row.narration}|{row.amount}|{row.direction}|{row.balance}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def parse_csv(path: str, fmt: str = "hdfc_like", source_bank: str | None = None) -> pd.DataFrame:
    cfg = BANK_FORMATS[fmt]
    raw = pd.read_csv(path, dtype=str)
    out = pd.DataFrame()
    out["txn_date"] = pd.to_datetime(raw[cfg["date"]], format=cfg["date_fmt"]).dt.date
    out["narration"] = raw[cfg["narration"]].fillna("").str.strip()
    debit, credit = _num(raw[cfg["debit"]]), _num(raw[cfg["credit"]])
    out["direction"] = (credit > 0).map({True: "credit", False: "debit"})
    out["amount"] = (credit + debit).round(2)
    out["balance"] = _num(raw[cfg["balance"]])
    out["source_bank"] = source_bank or fmt
    out["txn_id"] = out.apply(make_txn_id, axis=1)
    out = out[UNIFIED_COLUMNS]
    return out.drop_duplicates("txn_id").reset_index(drop=True)
