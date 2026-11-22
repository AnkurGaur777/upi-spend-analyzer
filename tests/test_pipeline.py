import re
import pytest
from sqlalchemy import create_engine, text
from spend_analyzer.pipeline import run

CSV_PATH = "data/raw/synthetic/statement_synthetic.csv"


def test_pipeline_run_twice(tmp_path, capsys):
    db_file = tmp_path / "t.db"
    engine = create_engine(f"sqlite:///{db_file}")

    # 1. First run
    df1, rec1 = run(CSV_PATH, engine=engine)
    out1 = capsys.readouterr().out
    m1 = re.search(r"inserted=(\d+)", out1)
    assert m1 is not None, f"Could not find inserted count in output: {out1}"
    inserted1 = int(m1.group(1))
    assert inserted1 == 704

    # 2. Second run
    df2, rec2 = run(CSV_PATH, engine=engine)
    out2 = capsys.readouterr().out
    m2 = re.search(r"inserted=(\d+)", out2)
    assert m2 is not None, f"Could not find inserted count in output: {out2}"
    inserted2 = int(m2.group(1))
    assert inserted2 == 0

    # 3. Database assertions
    with engine.connect() as conn:
        count_rows = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        assert count_rows == 704

        count_rec = conn.execute(text("SELECT COUNT(*) FROM recurring_payments")).scalar()
        assert count_rec == 6

        sum_transfer = conn.execute(text("SELECT SUM(is_transfer) FROM transactions")).scalar()
        assert sum_transfer == 21

        sum_refund = conn.execute(text("SELECT SUM(is_refund) FROM transactions")).scalar()
        assert sum_refund == 7


def test_partition_sums_to_total_rows(tmp_path):
    db_file = tmp_path / "part.db"
    engine = create_engine(f"sqlite:///{db_file}")
    df, rec = run(CSV_PATH, engine=engine)

    with engine.connect() as conn:
        total_rows = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        assert total_rows == 704

        spend_rows = conn.execute(
            text(
                "SELECT COUNT(*) FROM transactions "
                "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND category <> 'Investments'"
            )
        ).scalar()
        assert spend_rows == 652

        income_rows = conn.execute(
            text("SELECT COUNT(*) FROM transactions WHERE direction = 'credit' AND category = 'Income' AND is_transfer = 0")
        ).scalar()
        assert income_rows == 12

        transfer_rows = conn.execute(text("SELECT COUNT(*) FROM transactions WHERE is_transfer = 1")).scalar()
        assert transfer_rows == 21

        refund_rows = conn.execute(
            text("SELECT COUNT(*) FROM transactions WHERE is_refund = 1 OR is_reversal = 1")
        ).scalar()
        assert refund_rows == 7

        invest_rows = conn.execute(
            text("SELECT COUNT(*) FROM transactions WHERE direction = 'debit' AND category = 'Investments'")
        ).scalar()
        assert invest_rows == 12

        # Assert mutual exclusivity and exact completeness
        partition_sum = spend_rows + income_rows + transfer_rows + refund_rows + invest_rows
        assert partition_sum == total_rows == 704
