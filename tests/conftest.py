# tests/conftest.py
import json
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text

from spend_analyzer.pipeline import run as run_pipeline


@pytest.fixture(scope="session")
def test_db_engine(tmp_path_factory):
    """Session-scoped isolated SQLite engine with synthetic dataset loaded."""
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test_spend.db"
    engine = create_engine(f"sqlite:///{db_path}")

    csv_path = Path("data/raw/synthetic/statement_synthetic.csv")
    if not csv_path.exists():
        csv_path = Path(__file__).resolve().parent.parent / "data" / "raw" / "synthetic" / "statement_synthetic.csv"

    # Run full pipeline to populate transactions and recurring_payments
    run_pipeline(csv_path, engine=engine)

    # Create analytical views for SQLite
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS v_spend AS
            SELECT *
            FROM transactions
            WHERE direction = 'debit'
              AND is_transfer = 0
              AND is_reversal = 0
              AND category <> 'Investments';
        """))
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS v_income AS
            SELECT *
            FROM transactions
            WHERE direction = 'credit'
              AND category = 'Income'
              AND is_transfer = 0;
        """))
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS v_monthly_summary AS
            WITH months AS (
              SELECT DISTINCT txn_month FROM transactions
            ),
            inc AS (
              SELECT txn_month, SUM(amount) AS income
              FROM v_income
              GROUP BY txn_month
            ),
            sp AS (
              SELECT txn_month, SUM(amount) AS spend
              FROM v_spend
              GROUP BY txn_month
            ),
            inv AS (
              SELECT txn_month, SUM(amount) AS investments
              FROM transactions
              WHERE direction = 'debit' AND category = 'Investments'
              GROUP BY txn_month
            )
            SELECT
              m.txn_month,
              COALESCE(inc.income, 0.00) AS income,
              COALESCE(sp.spend, 0.00) AS spend,
              (COALESCE(inc.income, 0.00) - COALESCE(sp.spend, 0.00)) AS savings,
              ROUND((COALESCE(inc.income, 0.00) - COALESCE(sp.spend, 0.00)) / NULLIF(COALESCE(inc.income, 0.00), 0), 3) AS savings_rate,
              COALESCE(inv.investments, 0.00) AS investments
            FROM months m
            LEFT JOIN inc ON m.txn_month = inc.txn_month
            LEFT JOIN sp  ON m.txn_month = sp.txn_month
            LEFT JOIN inv ON m.txn_month = inv.txn_month
            ORDER BY m.txn_month;
        """))

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_conn(test_db_engine):
    """Session-scoped database connection."""
    with test_db_engine.connect() as conn:
        yield conn


@pytest.fixture(scope="session")
def memo_data():
    """Single source of truth metrics fixture."""
    memo_path = Path("docs/memo_numbers.json")
    if not memo_path.exists():
        memo_path = Path(__file__).resolve().parent.parent / "docs" / "memo_numbers.json"
    assert memo_path.exists(), f"{memo_path} does not exist!"
    return json.loads(memo_path.read_text(encoding="utf-8"))
