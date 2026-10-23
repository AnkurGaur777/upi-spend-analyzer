import pandas as pd
from spend_analyzer.categorize import (
    rule_category, categorize, load_rules,
    load_lexicon, lexicon_category, load_first_names, is_person_name
)
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
    assert set(df["cat_method"].unique()).issubset({"rule", "fuzzy", "lexicon", "p2p", "none"})


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


def test_lexicon_and_p2p_categorization():
    lexicon = load_lexicon("data/reference/category_lexicon.csv")
    names = load_first_names("data/reference/first_names.txt")
    rules = load_rules("data/reference/category_rules.csv")

    tiny_df = pd.DataFrame({
        "txn_date": ["2026-02-01"] * 7,
        "narration": [
            "UPI-GUPTA-gupta@icici-123456789012-Payment",
            "POS 416021XXXXXX1234 KUMAR MEDICAL HALL NEW DELHI",
            "POS 416021XXXXXX1234 M/S RK TRADERS NEW DELHI",
            "UPI-XYZ-xyz@icici-123456789012-Payment",
            "UPI-AMIT-amit@icici-123456789012-Payment",
            "UPI-AMIT-amit@icici-123456789012-Payment",
            "UPI-AMIT-amit@icici-123456789012-Rent share",
        ],
        "amount": [500.0, 300.0, 1000.0, 2000.0, 1500.0, 700.0, 5000.0],
        "direction": ["debit"] * 7,
        "balance": [50000.0] * 7,
        "source_bank": ["hdfc_like"] * 7,
        "txn_id": [f"id{i}" for i in range(1, 8)],
        "merchant": [
            "GUPTA PROVISION STORE",
            "KUMAR MEDICAL HALL",
            "M/S RK TRADERS",
            "XYZ ENTERPRISES",
            "AMIT",
            "AMIT KIRANA STORE",
            "AMIT",
        ],
        "txn_month": ["2026-02"] * 7,
        "weekday": ["Sunday"] * 7,
        "is_transfer": [False] * 7,
        "is_refund": [False] * 7,
        "is_reversal": [False] * 7,
    })

    res = categorize(tiny_df, rules, lexicon=lexicon, names=names)

    # 1. GUPTA PROVISION STORE -> Groceries via lexicon
    assert res.loc[0, "category"] == "Groceries"
    assert res.loc[0, "cat_method"] == "lexicon"

    # 2. KUMAR MEDICAL HALL -> Health
    assert res.loc[1, "category"] == "Health"
    assert res.loc[1, "cat_method"] == "lexicon"

    # 3. M/S RK TRADERS -> Other
    assert res.loc[2, "category"] == "Other"
    assert res.loc[2, "cat_method"] == "none"

    # 4. XYZ ENTERPRISES -> Other
    assert res.loc[3, "category"] == "Other"
    assert res.loc[3, "cat_method"] == "none"

    # 5. merchant AMIT -> Transfers (p2p)
    assert res.loc[4, "category"] == "Transfers"
    assert res.loc[4, "cat_method"] == "p2p"

    # 6. AMIT KIRANA STORE -> Groceries (lexicon wins over p2p)
    assert res.loc[5, "category"] == "Groceries"
    assert res.loc[5, "cat_method"] == "lexicon"

    # 7. Note "Rent share" does not change AMIT from Transfers to Rent
    assert res.loc[6, "category"] == "Transfers"
    assert res.loc[6, "cat_method"] == "p2p"
