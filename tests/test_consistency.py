# tests/test_consistency.py
import json
from pathlib import Path
import pandas as pd
import pytest


def test_row_partition_sums_to_704(db_conn, memo_data):
    """Mutually exclusive partition of all 704 rows."""
    tx_all = pd.read_sql("SELECT * FROM transactions", db_conn)
    assert len(tx_all) == 704

    part = memo_data["partition_reconciliation"]
    sum_parts = (
        part["spend_rows"]
        + part["income_rows"]
        + part["self_transfer_rows"]
        + part["refund_reversal_rows"]
        + part["investment_rows"]
        + part["other_rows"]
    )
    assert sum_parts == 704
    assert part["total_rows"] == 704
    assert part["spend_rows"] == 652
    assert part["income_rows"] == 12
    assert part["self_transfer_rows"] == 21
    assert part["refund_reversal_rows"] == 7
    assert part["investment_rows"] == 12
    assert part["other_rows"] == 0


def test_weekday_weekend_spend_and_days(db_conn, memo_data):
    """Weekday + weekend spend must equal living spend, and days sum to 362."""
    ctx = memo_data["context"]
    assert ctx["calendar_days"] == 362

    f4 = memo_data["findings"]["f4_weekend_vs_weekday"]
    assert f4["calendar_days"] == 362
    assert f4["weekend_days"] == 104
    assert f4["weekday_days"] == 258
    assert f4["weekend_days"] + f4["weekday_days"] == 362

    # Version A: All living spend
    ver_a = f4["version_a_all_living_spend"]
    assert round(ver_a["weekend_total"] + ver_a["weekday_total"], 2) == round(ctx["total_spend"], 2)
    assert ver_a["weekend_total"] == 172326.0
    assert ver_a["weekday_total"] == 473993.0
    assert ver_a["weekend_total"] + ver_a["weekday_total"] == 646319.0
    assert ver_a["weekend_per_day"] == 1656.98
    assert ver_a["weekday_per_day"] == 1837.18
    assert ver_a["weekday_higher_pct"] == 10.9

    # Version B: Variable spend (living spend excluding fixed commitments)
    ver_b = f4["version_b_variable_spend_excluding_fixed"]
    f1 = memo_data["findings"]["f1_subscriptions"]
    # Variable spend + fixed recurring living spend must equal total living spend
    assert round(ver_b["weekend_total"] + ver_b["weekday_total"] + f1["recurring_living_spend"], 2) == round(ctx["total_spend"], 2)
    assert ver_b["weekend_total"] == 93058.0
    assert ver_b["weekday_total"] == 306457.0
    assert ver_b["weekend_total"] + ver_b["weekday_total"] == 399515.0
    assert 399515.0 + 246804.0 == 646319.0
    assert ver_b["weekend_per_day"] == 894.79
    assert ver_b["weekday_per_day"] == 1187.82
    assert ver_b["weekday_higher_pct"] == 32.7


def test_monthly_savings_rates_match_db(db_conn, memo_data):
    """Every month's savings rate == (income - spend) / income from DB."""
    # Ensure v_monthly_summary exists
    try:
        m_summary = pd.read_sql("SELECT * FROM v_monthly_summary ORDER BY txn_month", db_conn)
    except Exception:
        # If view does not exist in SQLite session, query tables directly
        tx_sp = pd.read_sql(
            "SELECT txn_month, SUM(amount) as spend FROM transactions "
            "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND category <> 'Investments' "
            "GROUP BY txn_month",
            db_conn,
        )
        tx_inc = pd.read_sql(
            "SELECT txn_month, SUM(amount) as income FROM transactions "
            "WHERE direction = 'credit' AND category = 'Income' AND is_transfer = 0 "
            "GROUP BY txn_month",
            db_conn,
        )
        m_summary = pd.merge(tx_inc, tx_sp, on="txn_month")
        m_summary["savings"] = m_summary["income"] - m_summary["spend"]
        m_summary["savings_rate"] = (m_summary["savings"] / m_summary["income"]).round(3)

    assert len(m_summary) == 12
    for _, row in m_summary.iterrows():
        expected_rate = round((row["income"] - row["spend"]) / row["income"], 3)
        assert abs(row["savings_rate"] - expected_rate) < 0.001

    # November 2025 specifically
    nov = m_summary[m_summary["txn_month"] == "2025-11"].iloc[0]
    assert nov["income"] == 65000.0
    assert nov["spend"] == 60480.0
    assert nov["savings"] == 4520.0
    assert round(nov["savings_rate"], 3) == 0.070

    f5 = memo_data["findings"]["f5_savings_rate_drop"]
    assert f5["lowest_month"] == "2025-11"
    assert f5["lowest_month_spend"] == 60480.0
    assert f5["lowest_savings_rate_pct"] == 7.0


def test_food_delivery_matches_database(db_conn, memo_data):
    """Food delivery orders and spend match SWIGGY, ZOMATO, DOMINOS in DB."""
    food = pd.read_sql(
        "SELECT merchant, COUNT(*) as orders, SUM(amount) as spend FROM transactions "
        "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND merchant IN ('SWIGGY', 'ZOMATO', 'DOMINOS') "
        "GROUP BY merchant",
        db_conn,
    )
    total_orders = int(food["orders"].sum())
    total_spend = float(food["spend"].sum())

    assert total_orders == 129
    assert total_spend == 51565.0

    f2 = memo_data["findings"]["f2_food_delivery"]
    assert f2["orders_count"] == 129
    assert f2["total_spend"] == 51565.0
    assert f2["avg_ticket"] == 399.73


def test_recommendation_totals_sum_of_parts(memo_data):
    """Recommendation totals == sum of individual recommendation savings."""
    recs = memo_data["recommendations"]
    assert len(recs) == 3

    monthly_sum = sum(r["expected_monthly_saving"] for r in recs)
    annual_sum = sum(r["expected_annual_saving"] for r in recs)

    tot = memo_data["total_savings_potential"]
    assert round(tot["monthly"], 2) == round(monthly_sum, 2)
    assert round(tot["annual"], 2) == round(annual_sum, 2)

    assert recs[0]["expected_monthly_saving"] == 2148.54
    assert recs[0]["expected_annual_saving"] == 25782.50
    assert recs[1]["expected_monthly_saving"] == 768.00
    assert recs[1]["expected_annual_saving"] == 9216.00
    assert recs[2]["expected_monthly_saving"] == 922.50
    assert recs[2]["expected_annual_saving"] == 11070.00

    assert tot["monthly"] == 3839.04
    assert tot["annual"] == 46068.50

    # Unrounded percentage points test
    base_savings = memo_data["context"]["total_savings"]
    income = memo_data["context"]["total_income"]
    base_rate = base_savings / income
    proj_rate = (base_savings + tot["annual"]) / income
    pp_increase = round((proj_rate - base_rate) * 100, 1)
    assert tot["percentage_points_increase"] == pp_increase
    assert pp_increase == 5.9
    assert tot["projected_savings_rate_pct"] == 23.0


def test_discretionary_definition_matches_metric_definitions(db_conn, memo_data):
    """Discretionary definition matches Shopping, Food & Dining, Entertainment."""
    disc_cats = ["Shopping", "Food & Dining", "Entertainment"]
    assert memo_data["discretionary_definition"]["categories"] == disc_cats

    df = pd.read_sql(
        "SELECT category, SUM(amount) as spend FROM transactions "
        "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND category <> 'Investments' "
        "GROUP BY category",
        db_conn,
    )
    disc_spend = float(df[df["category"].isin(disc_cats)]["spend"].sum())
    assert disc_spend == 183607.0
    assert memo_data["discretionary_definition"]["discretionary_spend_total"] == 183607.0

    total_living_spend = memo_data["context"]["total_spend"]
    pct = round(100.0 * disc_spend / total_living_spend, 1)
    assert pct == 28.4
    assert memo_data["discretionary_definition"]["pct_of_living_spend"] == 28.4


def test_holdout_files_sha256_unmodified():
    """Assert hard holdout test dataset and reference labels are frozen and unmodified (normalized LF)."""
    import hashlib

    raw_path = Path("data/raw/synthetic/statement_hard_holdout.csv")
    ref_path = Path("data/reference/labelled_holdout_hard.csv")

    assert raw_path.exists(), f"{raw_path} missing!"
    assert ref_path.exists(), f"{ref_path} missing!"

    raw_bytes = raw_path.read_bytes().replace(b"\r\n", b"\n")
    ref_bytes = ref_path.read_bytes().replace(b"\r\n", b"\n")

    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    ref_sha = hashlib.sha256(ref_bytes).hexdigest()

    expected_raw_sha = "5683c77cec2631981423e11211491b066468054aa97dac5d03a568ee618eff3f"
    expected_ref_sha = "b1cb5cfcc02793dbbdebcdd9f4256071e51ad65a838220a1af1f66756a55151b"

    assert raw_sha == expected_raw_sha, f"Holdout raw file altered! Got {raw_sha}, expected {expected_raw_sha}"
    assert ref_sha == expected_ref_sha, f"Holdout reference file altered! Got {ref_sha}, expected {expected_ref_sha}"


def test_all_rendered_percentages_match_registry(memo_data):
    """Every percentage drawn in dashboard visuals must exist in memo_numbers.json percentages_registry."""
    import re

    rendered_path = Path("docs/audit/rendered_text.json")
    assert rendered_path.exists(), f"{rendered_path} missing!"

    strings = json.loads(rendered_path.read_text(encoding="utf-8"))
    registry = memo_data.get("percentages_registry", {})

    pct_pattern = re.compile(r"\b\d+(?:\.\d+)?%")
    found_pcts = set()
    unregistered = set()

    for s in strings:
        matches = pct_pattern.findall(s)
        for m in matches:
            found_pcts.add(m)
            if m not in registry:
                unregistered.add(m)

    assert not unregistered, f"Found unregistered percentages in rendered_text.json: {unregistered}"
    # Specific check: 42.7% and 23.4% were old invalid ratios and MUST NOT appear
    assert "42.7%" not in found_pcts, "42.7% erroneously present in rendered dashboard text!"
    assert "23.4%" not in found_pcts, "23.4% old percentage erroneously present in rendered dashboard text!"
    assert "39.1%" in found_pcts, "39.1% (Rent+SIP ratio) missing from rendered dashboard text!"
    assert "74.8%" in found_pcts, "74.8% (Top 4 share) missing from rendered dashboard text!"
    assert "23.0%" in found_pcts, "23.0% (projected savings rate) missing from rendered dashboard text!"


def test_weekday_weekend_per_day_gaps_computed_from_unrounded_values(memo_data):
    """Every per-day gap shown in docs is computed from unrounded sums / days."""
    f4 = memo_data["findings"]["f4_weekend_vs_weekday"]
    cats = f4["version_b_variable_spend_excluding_fixed"]["category_breakdown"]

    # Shopping specifically: 70,936/258 - 19,697/104 = 85.5515... -> 85.55 (not 85.56)
    shop = cats["Shopping"]
    assert shop["weekday_total"] == 70936.0
    assert shop["weekend_total"] == 19697.0
    assert shop["per_day_gap"] == 85.55

    for cat_name, info in cats.items():
        wk_unrounded = info["weekday_total"] / 258
        we_unrounded = info["weekend_total"] / 104
        expected_gap = round(wk_unrounded - we_unrounded, 2)
        assert info["per_day_gap"] == expected_gap, f"Gap mismatch for {cat_name}: {info['per_day_gap']} != {expected_gap}"


def test_discretionary_small_ticket_and_cafes(db_conn, memo_data):
    """Discretionary sub-300 debits (205 txns, Rs 38,871) and cafes (30 txns, Rs 5,893)."""
    # 1. Discretionary sub-300
    df_disc = pd.read_sql(
        "SELECT merchant, category, amount FROM transactions "
        "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 "
        "  AND category <> 'Investments' AND amount < 300 "
        "  AND merchant NOT IN (SELECT merchant FROM recurring_payments)",
        db_conn,
    )
    assert len(df_disc) == 205
    assert round(float(df_disc["amount"].sum()), 2) == 38871.0
    assert round(float(df_disc["amount"].mean()), 2) == 189.61

    f3 = memo_data["findings"]["f3_small_ticket_leaks"]
    assert f3["discretionary_sub300_count"] == 205
    assert f3["discretionary_sub300_total"] == 38871.0
    assert f3["discretionary_sub300_avg"] == 189.61
    assert f3["discretionary_sub300_monthly"] == 3239.25

    # 2. Cafes < 300
    df_cafes = pd.read_sql(
        "SELECT merchant, COUNT(*) as cnt, SUM(amount) as amt, AVG(amount) as avg_t "
        "FROM transactions "
        "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 "
        "  AND merchant IN ('CAFE COFFEE DAY', 'STARBUCKS') AND amount < 300 "
        "GROUP BY merchant",
        db_conn,
    )
    assert int(df_cafes["cnt"].sum()) == 30
    assert round(float(df_cafes["amt"].sum()), 2) == 5893.0
    assert f3["cafes_details"]["count"] == 30
    assert f3["cafes_details"]["total_amount"] == 5893.0


def test_page_metrics_ratios(memo_data):
    """Assert 39.1% Rent+SIP ratio and 74.8% unrounded Top 4 share."""
    pm = memo_data["page_metrics"]
    assert pm["page3_rent_plus_sip_pct"] == 39.1
    assert pm["page2_top4_share_pct"] == 74.8

    # Unrounded math verification
    total_spend = memo_data["context"]["total_spend"]
    rent_plus_sip = 216000.0 + 60000.0
    total_outflows = total_spend + 60000.0
    assert round(100.0 * rent_plus_sip / total_outflows, 1) == 39.1

    top4_sum = 216000.0 + 92979.0 + 90633.0 + 83599.0  # 483,211.0
    assert round(100.0 * top4_sum / total_spend, 1) == 74.8
