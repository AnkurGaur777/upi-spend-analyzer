from datetime import date, timedelta
import pandas as pd
from spend_analyzer.recurring import detect_recurring

EXPECTED_COLUMNS = [
    "merchant",
    "category",
    "frequency",
    "typical_amount",
    "n_payments",
    "first_seen",
    "last_seen",
    "annual_cost",
]


def test_netflix_monthly():
    # 12 monthly debits of 649 for "NETFLIX" roughly 30 days apart (+-2 days jitter)
    jitters = [0, 1, -1, 2, -2, 0, 1, -1, 2, -2, 0, 1]
    dates = []
    cur = date(2025, 1, 1)
    for j in jitters:
        dates.append(cur + timedelta(days=j))
        cur += timedelta(days=30)

    df = pd.DataFrame({
        "txn_date": dates,
        "merchant": ["NETFLIX"] * 12,
        "amount": [649.0] * 12,
        "direction": ["debit"] * 12,
        "category": ["Subscriptions"] * 12,
        "is_transfer": [False] * 12,
    })
    res = detect_recurring(df)
    assert len(res) == 1
    row = res.iloc[0]
    assert row["merchant"] == "NETFLIX"
    assert row["frequency"] == "monthly"
    assert row["annual_cost"] == 7788.0
    assert row["n_payments"] == 12
    assert row["typical_amount"] == 649.0
    assert list(res.columns) == EXPECTED_COLUMNS


def test_weekly_debits():
    # weekly debits of 200 for 10 weeks -> weekly, annual_cost 10400.0
    dates = [date(2025, 1, 1) + timedelta(days=7 * i) for i in range(10)]
    df = pd.DataFrame({
        "txn_date": dates,
        "merchant": ["GYM TRAINER"] * 10,
        "amount": [200.0] * 10,
        "direction": ["debit"] * 10,
        "category": ["Health"] * 10,
        "is_transfer": [False] * 10,
    })
    res = detect_recurring(df)
    assert len(res) == 1
    row = res.iloc[0]
    assert row["frequency"] == "weekly"
    assert row["annual_cost"] == 10400.0
    assert row["n_payments"] == 10


def test_amount_variation_not_detected():
    # monthly debits but alternating between 500 and 1500 -> NOT detected
    dates = [date(2025, 1, 1) + timedelta(days=30 * i) for i in range(10)]
    amounts = [500.0 if i % 2 == 0 else 1500.0 for i in range(10)]
    df = pd.DataFrame({
        "txn_date": dates,
        "merchant": ["VARIABLE STORE"] * 10,
        "amount": amounts,
        "direction": ["debit"] * 10,
        "category": ["Shopping"] * 10,
        "is_transfer": [False] * 10,
    })
    res = detect_recurring(df)
    assert len(res) == 0


def test_min_count_not_detected():
    # merchant with only 2 payments -> NOT detected
    df = pd.DataFrame({
        "txn_date": [date(2025, 1, 1), date(2025, 1, 31)],
        "merchant": ["FEW PAYMENTS"] * 2,
        "amount": [500.0, 500.0],
        "direction": ["debit"] * 2,
        "category": ["Bills & Utilities"] * 2,
        "is_transfer": [False] * 2,
    })
    res = detect_recurring(df)
    assert len(res) == 0


def test_is_transfer_ignored():
    # monthly debits flagged is_transfer=True -> NOT detected
    dates = [date(2025, 1, 1) + timedelta(days=30 * i) for i in range(6)]
    df = pd.DataFrame({
        "txn_date": dates,
        "merchant": ["SELF"] * 6,
        "amount": [5000.0] * 6,
        "direction": ["debit"] * 6,
        "category": ["Transfers"] * 6,
        "is_transfer": [True] * 6,
    })
    res = detect_recurring(df)
    assert len(res) == 0


def test_credits_not_detected():
    # credits are never detected as recurring
    dates = [date(2025, 1, 1) + timedelta(days=30 * i) for i in range(12)]
    df = pd.DataFrame({
        "txn_date": dates,
        "merchant": ["SALARY"] * 12,
        "amount": [65000.0] * 12,
        "direction": ["credit"] * 12,
        "category": ["Income"] * 12,
        "is_transfer": [False] * 12,
    })
    res = detect_recurring(df)
    assert len(res) == 0


def test_empty_input():
    empty_df = pd.DataFrame()
    res = detect_recurring(empty_df)
    assert list(res.columns) == EXPECTED_COLUMNS
    assert len(res) == 0


def test_most_frequent_category():
    # category column carries merchant's most frequent category
    dates = [date(2025, 1, 1) + timedelta(days=30 * i) for i in range(5)]
    categories = ["Subscriptions", "Subscriptions", "Entertainment", "Subscriptions", "Other"]
    df = pd.DataFrame({
        "txn_date": dates,
        "merchant": ["PRIME"] * 5,
        "amount": [299.0] * 5,
        "direction": ["debit"] * 5,
        "category": categories,
        "is_transfer": [False] * 5,
    })
    res = detect_recurring(df)
    assert len(res) == 1
    assert res.iloc[0]["category"] == "Subscriptions"
