# src/spend_analyzer/recurring.py
import numpy as np
import pandas as pd

PERIODS = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}
TOL = {"weekly": 2, "monthly": 4, "quarterly": 7, "yearly": 12}
OUTPUT_COLUMNS = [
    "merchant",
    "category",
    "frequency",
    "typical_amount",
    "n_payments",
    "first_seen",
    "last_seen",
    "annual_cost",
]


def detect_recurring(df: pd.DataFrame, min_count: int = 3, amount_tol: float = 0.05) -> pd.DataFrame:
    if df.empty or "direction" not in df.columns:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    debits = df[(df["direction"] == "debit")].copy()
    if "is_transfer" in debits.columns:
        debits = debits[~debits["is_transfer"].astype(bool)]
    if "is_reversal" in debits.columns:
        debits = debits[~debits["is_reversal"].astype(bool)]

    if debits.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    debits["txn_date"] = pd.to_datetime(debits["txn_date"])
    out = []
    for merchant, g in debits.groupby("merchant"):
        if len(g) < min_count:
            continue
        g = g.sort_values("txn_date")
        med = g["amount"].median()
        if med == 0 or (abs(g["amount"] - med) / med > amount_tol).mean() > 0.2:
            continue  # amounts vary too much to be a subscription
        gaps = g["txn_date"].diff().dt.days.dropna()
        if gaps.empty:
            continue
        gap = float(np.median(gaps))
        for name, days in PERIODS.items():
            if abs(gap - days) <= TOL[name]:
                per_year = {"weekly": 52, "monthly": 12, "quarterly": 4, "yearly": 1}[name]
                if "category" in g.columns and not g["category"].dropna().empty:
                    mode_val = g["category"].mode()
                    cat = mode_val.iloc[0] if not mode_val.empty else "Other"
                else:
                    cat = "Other"

                out.append({
                    "merchant": merchant,
                    "category": cat,
                    "frequency": name,
                    "typical_amount": round(med, 2),
                    "n_payments": len(g),
                    "first_seen": g["txn_date"].min().date(),
                    "last_seen": g["txn_date"].max().date(),
                    "annual_cost": round(med * per_year, 2),
                })
                break

    if out:
        res = pd.DataFrame(out).sort_values("annual_cost", ascending=False)
        return res[OUTPUT_COLUMNS].reset_index(drop=True)
    return pd.DataFrame(columns=OUTPUT_COLUMNS)
