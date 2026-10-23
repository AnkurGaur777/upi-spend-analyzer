from datetime import date
from spend_analyzer.parsers import parse_csv

SYNTHETIC_CSV = "data/raw/synthetic/statement_synthetic.csv"


def test_parse_csv_columns():
    df = parse_csv(SYNTHETIC_CSV)
    expected_columns = [
        "txn_date",
        "narration",
        "amount",
        "direction",
        "balance",
        "source_bank",
        "txn_id",
    ]
    assert list(df.columns) == expected_columns


def test_parse_csv_row_count():
    df = parse_csv(SYNTHETIC_CSV)
    assert len(df) == 704


def test_parse_csv_txn_id_unique():
    df = parse_csv(SYNTHETIC_CSV)
    assert df["txn_id"].is_unique


def test_parse_csv_no_nulls():
    df = parse_csv(SYNTHETIC_CSV)
    assert not df.isna().any().any()


def test_parse_csv_direction_values_and_counts():
    df = parse_csv(SYNTHETIC_CSV)
    assert set(df["direction"].unique()) == {"debit", "credit"}
    assert (df["direction"] == "debit").sum() == 676
    assert (df["direction"] == "credit").sum() == 28


def test_parse_csv_amounts_positive():
    df = parse_csv(SYNTHETIC_CSV)
    assert (df["amount"] > 0).all()


def test_parse_csv_date_range():
    df = parse_csv(SYNTHETIC_CSV)
    assert df["txn_date"].min() == date(2025, 10, 1)
    assert df["txn_date"].max() == date(2026, 9, 27)
    assert str(df["txn_date"].min()) == "2025-10-01"
    assert str(df["txn_date"].max()) == "2026-09-27"


def test_parse_csv_deterministic():
    df1 = parse_csv(SYNTHETIC_CSV)
    df2 = parse_csv(SYNTHETIC_CSV)
    assert list(df1["txn_id"]) == list(df2["txn_id"])
