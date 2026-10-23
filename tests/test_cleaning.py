import pandas as pd
from spend_analyzer.cleaning import extract_merchant, clean
from spend_analyzer.parsers import parse_csv


def test_upi_merchant():
    assert extract_merchant("UPI-SWIGGY-swiggy@icici-ICIC0000123-412345678901-Payment") == "SWIGGY"


def test_neft_merchant():
    assert extract_merchant("NEFT CR-ACME TECH PVT LTD-SALARY").startswith("ACME TECH")


def test_atw_merchant():
    assert extract_merchant("ATW-553014-NEW DELHI") == "ATM CASH"


def test_ach_merchant():
    assert extract_merchant("ACH D- HDFC MUTUAL FUND-SIP").startswith("HDFC MUTUAL FUND")


def test_billdesk_merchant():
    assert extract_merchant("BILLDESK-BSES RAJDHANI POWER").startswith("BSES")


def test_is_transfer():
    df = pd.DataFrame({
        "txn_date": ["2025-10-01"] * 4,
        "narration": [
            "NEFT CR-SELF-TOPUP",
            "UPI-PAPA-papa@icici-ICIC0000123-412345678901-Family",
            "UPI-SWIGGY-swiggy@icici-ICIC0000123-412345678901-Payment",
            "CARD SPEND AT SELFIE STUDIO",
        ],
        "amount": [100.0, 200.0, 300.0, 400.0],
        "direction": ["credit", "debit", "debit", "debit"],
        "balance": [1000.0, 800.0, 500.0, 100.0],
        "source_bank": ["bank"] * 4,
        "txn_id": ["id1", "id2", "id3", "id4"],
    })
    res = clean(df)
    assert res["is_transfer"].tolist() == [True, True, False, False]


def test_is_refund():
    df = pd.DataFrame({
        "txn_date": ["2025-10-01", "2025-10-02"],
        "narration": [
            "UPI-AMAZON REFUND-amazon@icici-ICIC0000123-412345678901-Refund",
            "UPI-AMAZON REFUND-amazon@icici-ICIC0000123-412345678901-Refund",
        ],
        "amount": [500.0, 500.0],
        "direction": ["credit", "debit"],
        "balance": [1500.0, 1000.0],
        "source_bank": ["bank"] * 2,
        "txn_id": ["id1", "id2"],
    })
    res = clean(df)
    assert res["is_refund"].tolist() == [True, False]


def test_is_reversal():
    df = pd.DataFrame({
        "txn_date": ["2025-10-01", "2025-10-01", "2025-10-01", "2025-10-04"],
        "narration": ["FAILED UPI", "REVERSAL", "OTHER EXPENSE", "LATE CREDIT"],
        "amount": [500.0, 500.0, 700.0, 500.0],
        "direction": ["debit", "credit", "debit", "credit"],
        "balance": [1000.0, 1500.0, 800.0, 1300.0],
        "source_bank": ["bank"] * 4,
        "txn_id": ["id1", "id2", "id3", "id4"],
    })
    res = clean(df)
    assert res["is_reversal"].tolist() == [True, True, False, False]


def test_clean_synthetic():
    raw_df = parse_csv("data/raw/synthetic/statement_synthetic.csv")
    df = clean(raw_df)
    assert len(df) == 704
    expected_added = ["merchant", "txn_month", "weekday", "is_transfer", "is_refund", "is_reversal"]
    for col in expected_added:
        assert col in df.columns
    assert list(df.columns) == list(raw_df.columns) + expected_added
