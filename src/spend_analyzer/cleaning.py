# src/spend_analyzer/cleaning.py
import re
import pandas as pd

TRANSFER_KEYWORDS = ("SELF", "PAPA")
TRANSFER_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in TRANSFER_KEYWORDS) + r")\b", re.I)

UPI_RE = re.compile(r"^UPI[-/](?P<name>[^-/@]+)", re.I)
PREFIX_RE = re.compile(r"^(NEFT DR|NEFT CR|NEFT|IMPS|RTGS|ACH D|ACH C|BILLDESK|ATW|NWD|POS)[\s\-/]*", re.I)
NOISE_RE = re.compile(r"\b\d{6,}\b|\b[A-Z]{4}0\w{6}\b")


def extract_merchant(narration: str) -> str:
    s = (narration or "").upper().strip()
    if s.startswith("ATW") or s.startswith("NWD"):
        return "ATM CASH"
    m = UPI_RE.match(s)
    if m:
        return " ".join(m.group("name").split())
    s = PREFIX_RE.sub("", s)
    s = NOISE_RE.sub("", s)
    s = re.sub(r"[^A-Z ]", " ", s)
    return " ".join(s.split()[:3])


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["merchant"] = df["narration"].map(extract_merchant)
    df["txn_month"] = pd.to_datetime(df["txn_date"]).dt.to_period("M").astype(str)
    df["weekday"] = pd.to_datetime(df["txn_date"]).dt.day_name()
    df["is_transfer"] = df["narration"].fillna("").astype(str).str.contains(TRANSFER_RE, regex=True)
    df["is_refund"] = (df["direction"] == "credit") & (
        df["narration"].fillna("").astype(str).str.upper().str.contains("REFUND", regex=False)
    )

    # is_reversal: debit and credit of same amount within 1 day, credit after debit
    sorted_df = df.copy()
    sorted_df["dt"] = pd.to_datetime(sorted_df["txn_date"])
    sorted_df["orig_pos"] = range(len(df))
    sorted_df = sorted_df.sort_values("dt", kind="stable")

    used_pos = set()
    rows = list(sorted_df.itertuples())
    for i, r_debit in enumerate(rows):
        if r_debit.orig_pos in used_pos or r_debit.direction != "debit":
            continue
        for r_credit in rows[i + 1 :]:
            if r_credit.orig_pos in used_pos:
                continue
            days = (r_credit.dt - r_debit.dt).days
            if days > 1:
                break
            if r_credit.direction == "credit" and r_credit.amount == r_debit.amount:
                used_pos.add(r_debit.orig_pos)
                used_pos.add(r_credit.orig_pos)
                break

    df["is_reversal"] = [i in used_pos for i in range(len(df))]
    return df
