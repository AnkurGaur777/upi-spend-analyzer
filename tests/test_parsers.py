from datetime import date
from pathlib import Path
import pytest
from spend_analyzer.parsers import (
    parse_csv,
    detect_bank_format,
    UNIFIED_COLUMNS,
    BANK_FORMATS,
)

SYNTHETIC_CSV = "data/raw/synthetic/statement_synthetic.csv"
ICICI_CSV = "data/raw/synthetic/statement_icici_like.csv"


def test_parse_csv_columns():
    df = parse_csv(SYNTHETIC_CSV)
    assert list(df.columns) == UNIFIED_COLUMNS


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


def test_parse_icici_like_columns():
    df = parse_csv(ICICI_CSV, fmt="icici_like")
    assert list(df.columns) == UNIFIED_COLUMNS


def test_both_parsers_produce_identical_unified_schema():
    df_hdfc = parse_csv(SYNTHETIC_CSV, fmt="hdfc_like")
    df_icici = parse_csv(ICICI_CSV, fmt="icici_like")
    assert list(df_hdfc.columns) == list(df_icici.columns)
    assert list(df_hdfc.columns) == UNIFIED_COLUMNS


def test_both_parsers_same_transactions_totals():
    df_hdfc = parse_csv(SYNTHETIC_CSV, fmt="hdfc_like")
    df_icici = parse_csv(ICICI_CSV, fmt="icici_like")

    assert len(df_hdfc) == len(df_icici) == 704
    assert df_hdfc["amount"].sum() == pytest.approx(df_icici["amount"].sum())
    assert (df_hdfc["direction"] == "debit").sum() == (df_icici["direction"] == "debit").sum()
    assert (df_hdfc["direction"] == "credit").sum() == (df_icici["direction"] == "credit").sum()
    assert df_hdfc[df_hdfc["direction"] == "debit"]["amount"].sum() == pytest.approx(
        df_icici[df_icici["direction"] == "debit"]["amount"].sum()
    )
    assert df_hdfc[df_hdfc["direction"] == "credit"]["amount"].sum() == pytest.approx(
        df_icici[df_icici["direction"] == "credit"]["amount"].sum()
    )
    # The transaction IDs and order of records match exactly
    assert list(df_hdfc["txn_id"]) == list(df_icici["txn_id"])


def test_auto_detect_bank_format():
    assert detect_bank_format(SYNTHETIC_CSV) == "hdfc_like"
    assert detect_bank_format(ICICI_CSV) == "icici_like"

    df_auto_hdfc = parse_csv(SYNTHETIC_CSV)
    df_auto_icici = parse_csv(ICICI_CSV)
    assert len(df_auto_hdfc) == 704
    assert len(df_auto_icici) == 704
    assert df_auto_hdfc["source_bank"].iloc[0] == "hdfc_like"
    assert df_auto_icici["source_bank"].iloc[0] == "icici_like"


def test_explicit_bank_arg():
    df_hdfc = parse_csv(SYNTHETIC_CSV, bank="hdfc_like")
    df_icici = parse_csv(ICICI_CSV, bank="icici_like")
    assert len(df_hdfc) == 704
    assert len(df_icici) == 704


def test_bad_file_raises_clear_error(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("ColA,ColB,ColC\n1,2,3\n")

    # Auto-detect fails
    with pytest.raises(ValueError, match="Unrecognized statement format"):
        parse_csv(bad_csv)

    # Explicit format fails with missing required columns
    with pytest.raises(ValueError, match="missing required columns"):
        parse_csv(bad_csv, fmt="hdfc_like")


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        parse_csv("nonexistent_path_statement.csv")
