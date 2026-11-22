# src/spend_analyzer/load.py
import os
import re
import sys
from pathlib import Path
import dotenv
import pandas as pd
from sqlalchemy import create_engine, inspect, text


def mask_db_url(url: str) -> str:
    """Mask credentials in database URL for safe logging."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def get_engine(url: str | None = None):
    dotenv.load_dotenv()
    db_url = url or os.getenv("DATABASE_URL", "mysql+pymysql://spend:spendpass@localhost:3306/spend_db")
    if db_url and "mysql" in db_url:
        try:
            eng = create_engine(db_url)
            with eng.connect() as conn:
                pass
            masked = mask_db_url(db_url)
            print(f"DATABASE INFO: Successfully connected to MySQL at {masked}")
            return eng
        except Exception as e:
            masked = mask_db_url(db_url)
            print(f"WARNING: MySQL at {masked} is unreachable. Active Database: SQLite fallback ('sqlite:///spend.db')")
            return create_engine("sqlite:///spend.db")

    print("WARNING: Using SQLite fallback engine ('sqlite:///spend.db')")
    return create_engine(db_url or "sqlite:///spend.db")


def load_transactions(df: pd.DataFrame, engine) -> int:
    """Idempotent: re-running with the same file inserts nothing twice."""
    cols = [
        "txn_id", "txn_date", "txn_month", "weekday", "narration", "merchant",
        "amount", "direction", "balance", "category", "cat_method",
        "is_transfer", "is_refund", "is_reversal", "source_bank"
    ]
    df_to_load = df.copy()
    for flag in ["is_transfer", "is_refund", "is_reversal"]:
        if flag in df_to_load.columns:
            df_to_load[flag] = df_to_load[flag].astype(int)
        else:
            df_to_load[flag] = 0

    with engine.begin() as conn:
        insp = inspect(conn)
        has_table = insp.has_table("transactions")
        if has_table:
            existing = set(pd.read_sql(text("SELECT txn_id FROM transactions"), conn)["txn_id"])
        else:
            existing = set()

        new = df_to_load[~df_to_load["txn_id"].isin(existing)][cols]
        if len(new) > 0:
            new.to_sql("transactions", conn, if_exists="append", index=False)
    return len(new)


def load_recurring(rec: pd.DataFrame, engine) -> int:
    cols = [
        "merchant", "category", "frequency", "typical_amount",
        "n_payments", "first_seen", "last_seen", "annual_cost"
    ]
    rec_to_load = rec[cols].copy() if not rec.empty else pd.DataFrame(columns=cols)

    with engine.begin() as conn:
        insp = inspect(conn)
        has_table = insp.has_table("recurring_payments")
        if not has_table:
            rec_to_load.head(0).to_sql("recurring_payments", conn, if_exists="append", index=False)
        else:
            conn.execute(text("DELETE FROM recurring_payments"))

        if not rec_to_load.empty:
            rec_to_load.to_sql("recurring_payments", conn, if_exists="append", index=False)
    return len(rec_to_load)
