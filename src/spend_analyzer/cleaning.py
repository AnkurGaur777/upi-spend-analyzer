# src/spend_analyzer/cleaning.py
import re
import pandas as pd

TRANSFER_KEYWORDS = ("SELF", "PAPA")
TRANSFER_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in TRANSFER_KEYWORDS) + r")\b", re.I)

UPI_RE = re.compile(r"^UPI[-/](?P<name>[^-/@]+)", re.I)
PREFIX_RE = re.compile(r"^(NEFT DR|NEFT CR|NEFT|IMPS|RTGS|ACH D|ACH C|BILLDESK|ATW|NWD|POS)[\s\-/]*", re.I)
NOISE_RE = re.compile(r"\b\d{6,}\b|\b[A-Z]{4}0\w{6}\b")

CARD_MASK_RE = re.compile(r"\b\w*X{4,}\w*\b", re.I)
CITIES = (
    "NEW DELHI", "DELHI", "MUMBAI", "BANGALORE", "BENGALURU",
    "GURGAON", "GURUGRAM", "NOIDA", "PUNE", "HYDERABAD", "CHENNAI", "KOLKATA"
)
CITY_SUFFIX_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in sorted(CITIES, key=len, reverse=True)) + r")$",
    re.I
)


def extract_merchant(narration: str) -> str:
    s = (narration or "").upper().strip()
    if s.startswith("ATW") or s.startswith("NWD"):
        return "ATM CASH"

    # Multi-format slash-separated UPI variants (e.g. UPI/<ref>/<name>/... or UPI/CR/<ref>/<name>/...)
    if s.startswith("UPI/") or s.startswith("UPI-"):
        if "/" in s:
            parts = [p.strip() for p in s.split("/") if p.strip()]
            for p in parts[1:]:
                if p in ("CR", "DR", "P2A", "P2P", "P2M", "UPI"):
                    continue
                if re.fullmatch(r"\d+", p):  # RRN or numerical reference
                    continue
                if "@" in p:
                    p = p.split("@")[0]
                cleaned_p = re.sub(r"[^A-Z ]", " ", p).strip()
                if cleaned_p and len(cleaned_p) >= 2:
                    return " ".join(cleaned_p.split()[:3])

    # Standard UPI-NAME-... format
    m = UPI_RE.match(s)
    if m:
        return " ".join(m.group("name").split())

    # IMPS or NEFT slash variants (e.g. IMPS/P2A/<ref>/<name>)
    if s.startswith("IMPS/") or s.startswith("NEFT/"):
        parts = [p.strip() for p in s.split("/") if p.strip()]
        for p in parts[1:]:
            if p in ("P2A", "P2P", "P2M", "CR", "DR"):
                continue
            if re.fullmatch(r"\d+", p):
                continue
            cleaned_p = re.sub(r"[^A-Z ]", " ", p).strip()
            if cleaned_p and len(cleaned_p) >= 2:
                return " ".join(cleaned_p.split()[:3])

    s = PREFIX_RE.sub("", s)
    s = CARD_MASK_RE.sub(" ", s)
    s = NOISE_RE.sub(" ", s)
    s = re.sub(r"[^A-Z ]", " ", s)
    s = " ".join(s.split())
    m_city = CITY_SUFFIX_RE.search(s)
    if m_city:
        candidate = s[:m_city.start()].strip()
        if candidate:
            s = candidate
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

    df["is_reversal"] = df.index.isin(used_pos)
    return df
