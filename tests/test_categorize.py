import pandas as pd
from spend_analyzer.categorize import rule_category, categorize, load_rules
from spend_analyzer.parsers import parse_csv
from spend_analyzer.cleaning import clean

RULES = [("AMAZON REFUND", "Shopping"), ("AMAZON", "Shopping"), ("NETFLIX", "Subscriptions")]

ALLOWED_CATEGORIES = {
    "Food & Dining", "Groceries", "Transport", "Shopping",
    "Bills & Utilities", "Rent", "Subscriptions", "Health",
    "Entertainment", "Investments", "Cash Withdrawal", "Transfers",
    "Income", "Other"
}


def test_rule_match():
    assert rule_category("UPI-NETFLIX-xyz", RULES) == "Subscriptions"


def test_no_match():
    assert rule_category("UPI-RANDOM SHOP", RULES) is None


def test_amazon_refund_rule():
    assert (
        rule_category(
            "UPI-AMAZON REFUND-amazon@icici-ICIC0000123-412345678901-Refund",
            RULES,
        )
        == "Shopping"
    )


def test_rule_category_whole_word():
    assert rule_category("UPI-COLA STALL-cola@icici", [("OLA", "Transport")]) is None
    assert rule_category("UPI-OLA-ola@icici-ICIC0000123", [("OLA", "Transport")]) == "Transport"


def test_load_rules_categories():
    rules = load_rules("data/reference/category_rules.csv")
    assert isinstance(rules, list)
    assert len(rules) > 0
    for item in rules:
        assert isinstance(item, tuple)
        assert len(item) == 2
        kw, cat = item
        assert isinstance(kw, str)
        assert isinstance(cat, str)
        assert cat in ALLOWED_CATEGORIES


def test_categorize_synthetic():
    raw = parse_csv("data/raw/synthetic/statement_synthetic.csv")
    cleaned = clean(raw)
    rules = load_rules("data/reference/category_rules.csv")
    df = categorize(cleaned, rules)
    assert len(df) == 704
    assert df["category"].notna().all()
    assert set(df["cat_method"].unique()).issubset({"rule", "fuzzy", "none"})


def test_fuzzy_matching():
    tiny_df = pd.DataFrame({
        "txn_date": ["2025-10-01", "2025-10-02"],
        "narration": ["UPI-X", "UPI-COLA"],
        "amount": [649.0, 50.0],
        "direction": ["debit", "debit"],
        "balance": [10000.0, 9950.0],
        "source_bank": ["hdfc_like", "hdfc_like"],
        "txn_id": ["id1", "id2"],
        "merchant": ["NETFLIX INDIA", "COLA STALL"],
        "txn_month": ["2025-10", "2025-10"],
        "weekday": ["Wednesday", "Thursday"],
        "is_transfer": [False, False],
        "is_refund": [False, False],
        "is_reversal": [False, False],
    })
    rules = [("NETFLIX", "Subscriptions"), ("OLA", "Transport")]
    res = categorize(tiny_df, rules)
    assert res.loc[0, "category"] == "Subscriptions"
    assert res.loc[1, "category"] != "Transport"
