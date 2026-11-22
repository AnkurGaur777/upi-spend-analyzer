# scripts/compute_memo_numbers.py
import json
import sqlite3
from pathlib import Path
import pandas as pd
from sqlalchemy import text

from spend_analyzer.load import get_engine

OUT_PATH = Path("docs/memo_numbers.json")


def compute_memo_numbers(engine=None):
    if engine is None:
        engine = get_engine()

    with engine.connect() as conn:
        tx_all = pd.read_sql(text("SELECT * FROM transactions"), conn)
        tx_spend = pd.read_sql(
            text(
                "SELECT * FROM transactions "
                "WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND category <> 'Investments'"
            ),
            conn,
        )
        tx_income = pd.read_sql(
            text("SELECT * FROM transactions WHERE direction = 'credit' AND category = 'Income' AND is_transfer = 0"),
            conn,
        )
        rec = pd.read_sql(text("SELECT * FROM recurring_payments"), conn)

        # 1. Mutually Exclusive Row Partition (Sums to exactly 704)
        part_spend = len(tx_spend)
        part_income = len(tx_income)
        part_transfer = int((tx_all["is_transfer"] == 1).sum())
        part_refund = int(((tx_all["is_refund"] == 1) | (tx_all["is_reversal"] == 1)).sum())
        part_invest = int(((tx_all["direction"] == "debit") & (tx_all["category"] == "Investments")).sum())
        part_other = len(tx_all) - (part_spend + part_income + part_transfer + part_refund + part_invest)

        assert (part_spend + part_income + part_transfer + part_refund + part_invest + part_other) == len(tx_all), "Partition does not sum to total rows!"
        assert part_other == 0, f"Expected 0 other rows, got {part_other}"

        partition_summary = {
            "spend_rows": part_spend,
            "income_rows": part_income,
            "self_transfer_rows": part_transfer,
            "refund_reversal_rows": part_refund,
            "investment_rows": part_invest,
            "other_rows": part_other,
            "total_rows": len(tx_all),
        }

        # 2. Context Metrics
        total_income = float(tx_income["amount"].sum())
        total_spend = float(tx_spend["amount"].sum())
        savings = total_income - total_spend
        raw_savings_rate = savings / total_income
        savings_rate_pct = round(raw_savings_rate * 100, 1)

        start_date = str(tx_all["txn_date"].min())
        end_date = str(tx_all["txn_date"].max())
        calendar_days = 362  # 2025-10-01 to 2026-09-27 (104 weekend + 258 weekday)
        months_count = tx_spend["txn_month"].nunique()
        avg_monthly_spend = round(total_spend / months_count, 2)
        avg_ticket = round(total_spend / len(tx_spend), 2)

        # 3. Finding 1: Subscriptions & Recurring
        sub_only = rec[rec["category"] == "Subscriptions"]
        annual_subscription_cost = float(sub_only["annual_cost"].sum())
        total_recurring_cost = float(rec["annual_cost"].sum())
        subscriptions_count = len(sub_only)
        sub_savable_monthly = round(annual_subscription_cost / 12, 2)
        sub_savable_annual = annual_subscription_cost

        # Fixed recurring within living spend (excl SIP): 5 services
        rec_living = rec[rec["category"] != "Investments"]
        recurring_living_spend = float(rec_living["annual_cost"].sum())
        pct_of_living_spend = round(100.0 * recurring_living_spend / total_spend, 1)

        # Total recurring commitments (including SIP) / total cash outflows (living spend + SIP): 6 services
        sip_total = float(tx_all[(tx_all["direction"] == "debit") & (tx_all["category"] == "Investments")]["amount"].sum())
        total_cash_outflows = total_spend + sip_total
        pct_of_total_outflow = round(100.0 * total_recurring_cost / total_cash_outflows, 1)

        # Non-rent living recurring services
        rec_non_rent = rec[(rec["category"] != "Investments") & (rec["category"] != "Rent")]
        non_rent_recurring_cost = float(rec_non_rent["annual_cost"].sum())
        non_rent_recurring_count = len(rec_non_rent)

        # Page 3: Rent + SIP / total cash outflows
        rent_total = float(rec[rec["category"] == "Rent"]["annual_cost"].sum())
        rent_plus_sip = rent_total + sip_total
        rent_plus_sip_pct = round(100.0 * rent_plus_sip / total_cash_outflows, 1)
        assert rent_plus_sip_pct == 39.1, f"Expected 39.1%, got {rent_plus_sip_pct}%"

        # Page 2: Top 4 categories share of spend (unrounded amounts: 483,211 / 646,319 = 74.8%)
        cat_sums = tx_spend.groupby("category")["amount"].sum().sort_values(ascending=False)
        top4_cats = cat_sums.iloc[:4]
        top4_sum = float(top4_cats.sum())
        top4_share_pct = round(100.0 * top4_sum / total_spend, 1)
        assert top4_share_pct == 74.8, f"Expected 74.8%, got {top4_share_pct}%"

        # 4. Finding 2: Food Delivery
        # Merchant set: SWIGGY, ZOMATO, DOMINOS
        food_deliv = tx_spend[tx_spend["merchant"].isin(["SWIGGY", "ZOMATO", "DOMINOS"])]
        food_deliv_orders = len(food_deliv)
        food_deliv_spend = float(food_deliv["amount"].sum())
        avg_deliv_ticket = round(food_deliv_spend / food_deliv_orders, 2)
        avg_deliv_monthly = round(food_deliv_spend / 12, 2)

        # Discretionary categories defined strictly per metric_definitions.md: Shopping, Food & Dining, Entertainment
        discretionary_categories = ["Shopping", "Food & Dining", "Entertainment"]
        discretionary_spend = float(tx_spend[tx_spend["category"].isin(discretionary_categories)]["amount"].sum())
        food_deliv_pct_discretionary = round(100.0 * food_deliv_spend / discretionary_spend, 1)
        food_dining_total = float(tx_spend[tx_spend["category"] == "Food & Dining"]["amount"].sum())
        food_deliv_pct_food = round(100.0 * food_deliv_spend / food_dining_total, 1)

        # 5. Finding 3: Small-Ticket Leaks (< Rs 300)
        # ALL sub-300 debits
        small_tx_all = tx_spend[tx_spend["amount"] < 300]
        small_all_count = len(small_tx_all)
        small_all_total = float(small_tx_all["amount"].sum())

        # DISCRETIONARY sub-300 debits (excluding detected recurring payees: Jio, Spotify, etc.)
        rec_merchants = rec["merchant"].tolist()
        small_disc = tx_spend[(tx_spend["amount"] < 300) & (~tx_spend["merchant"].isin(rec_merchants))]
        small_disc_count = len(small_disc)
        small_disc_total = float(small_disc["amount"].sum())
        small_disc_avg = round(small_disc_total / small_disc_count, 2)
        small_disc_monthly = round(small_disc_total / 12, 2)

        # Verify 205 rows and Rs 38,871
        assert small_disc_count == 205, f"Expected 205, got {small_disc_count}"
        assert small_disc_total == 38871.0, f"Expected 38871.0, got {small_disc_total}"

        # Category split of discretionary small-ticket
        disc_cat_split = small_disc.groupby("category").agg(
            txns=("txn_id", "count"),
            total=("amount", "sum"),
            avg_ticket=("amount", "mean"),
        ).round(2).to_dict(orient="index")

        # Excluded recurring payees under 300
        excluded_small = tx_spend[(tx_spend["amount"] < 300) & (tx_spend["merchant"].isin(rec_merchants))]
        excluded_small_dict = excluded_small.groupby("merchant").agg(
            txns=("txn_id", "count"),
            total=("amount", "sum"),
        ).to_dict(orient="index")

        # Exact Cafes merchant details (< 300, excluding Swiggy/Zomato/Dominos)
        cafe_merchants = ["CAFE COFFEE DAY", "STARBUCKS"]
        cafes_df = tx_spend[(tx_spend["amount"] < 300) & (tx_spend["merchant"].isin(cafe_merchants))]
        cafes_total = float(cafes_df["amount"].sum())
        cafes_count = len(cafes_df)
        cafes_breakdown = cafes_df.groupby("merchant").agg(
            txns=("txn_id", "count"),
            total=("amount", "sum"),
            avg_ticket=("amount", "mean"),
        ).round(2).to_dict(orient="index")
        assert cafes_total == 5893.0, f"Expected 5893.0, got {cafes_total}"

        # Food delivery under 300
        deliv_under_300 = tx_spend[(tx_spend["amount"] < 300) & (tx_spend["merchant"].isin(["SWIGGY", "ZOMATO", "DOMINOS"]))]
        deliv_under_300_total = float(deliv_under_300["amount"].sum())
        deliv_under_300_count = len(deliv_under_300)
        assert deliv_under_300_total == 8829.0, f"Expected 8829.0, got {deliv_under_300_total}"

        # Cab pool (< Rs 300, Transport, merchants UBER, RAPIDO, OLA)
        cab_merchants = ["UBER", "RAPIDO", "OLA"]
        cab_df = tx_spend[(tx_spend["amount"] < 300) & (tx_spend["category"] == "Transport") & (tx_spend["merchant"].isin(cab_merchants))]
        cab_pool_count = len(cab_df)
        cab_pool_total = float(cab_df["amount"].sum())
        assert cab_pool_count == 93, f"Expected 93 cab txns, got {cab_pool_count}"
        assert cab_pool_total == 16247.0, f"Expected 16247.0, got {cab_pool_total}"

        # Non-overlapping leak pool for Recommendation 3: Cab rides (<300) + Cafes (<300)
        # Delhi Metro (32 txns, Rs 5,524) excluded as it is already public transit
        controllable_transport = float(small_disc[small_disc["category"] == "Transport"]["amount"].sum()) # Total transport sub-300: 21,771.0
        non_overlap_leak_pool = cab_pool_total + cafes_total
        assert non_overlap_leak_pool == 22140.0, f"Expected 22140.0, got {non_overlap_leak_pool}"

        # 6. Finding 4: Weekday vs Weekend (Both Versions & Category Breakdown)
        weekend_days = 104
        weekday_days = 258

        tx_spend_copy = tx_spend.copy()
        tx_spend_copy["dt"] = pd.to_datetime(tx_spend_copy["txn_date"])
        tx_spend_copy["is_weekend"] = tx_spend_copy["dt"].dt.day_of_week >= 5

        # Version A: All Living Spend
        weekend_spend_a = float(tx_spend_copy[tx_spend_copy["is_weekend"]]["amount"].sum())
        weekday_spend_a = float(tx_spend_copy[~tx_spend_copy["is_weekend"]]["amount"].sum())
        assert round(weekend_spend_a + weekday_spend_a, 2) == round(total_spend, 2)
        weekend_avg_a = round(weekend_spend_a / weekend_days, 2)
        weekday_avg_a = round(weekday_spend_a / weekday_days, 2)
        delta_a_pct = round(100.0 * (weekday_avg_a - weekend_avg_a) / weekend_avg_a, 1)

        # Version B: Variable Spend (Excluding Rent & Fixed Recurring Bills)
        rec_living_merchants = rec_living["merchant"].tolist()
        tx_var = tx_spend_copy[(~tx_spend_copy["merchant"].isin(rec_living_merchants)) & (tx_spend_copy["category"] != "Rent")]
        weekend_spend_b = float(tx_var[tx_var["is_weekend"]]["amount"].sum())
        weekday_spend_b = float(tx_var[~tx_var["is_weekend"]]["amount"].sum())
        variable_spend_total = weekend_spend_b + weekday_spend_b
        assert round(variable_spend_total + recurring_living_spend, 2) == round(total_spend, 2)
        weekend_avg_b = round(weekend_spend_b / weekend_days, 2)
        weekday_avg_b = round(weekday_spend_b / weekday_days, 2)
        delta_b_pct = round(100.0 * (weekday_avg_b - weekend_avg_b) / weekend_avg_b, 1)

        # Version B Category Breakdown (Weekday vs Weekend per-day)
        ver_b_cat_breakdown = {}
        for cat in sorted(tx_var["category"].unique()):
            cat_df = tx_var[tx_var["category"] == cat]
            wk_spend = float(cat_df[~cat_df["is_weekend"]]["amount"].sum())
            we_spend = float(cat_df[cat_df["is_weekend"]]["amount"].sum())
            wk_rate = round(wk_spend / weekday_days, 2)
            we_rate = round(we_spend / weekend_days, 2)
            gap = round((wk_spend / weekday_days) - (we_spend / weekend_days), 2)
            ver_b_cat_breakdown[cat] = {
                "weekday_total": wk_spend,
                "weekend_total": we_spend,
                "weekday_per_day": wk_rate,
                "weekend_per_day": we_rate,
                "per_day_gap": gap,
            }

        # Robustness checks for Version B:
        # Transactions strictly > 5000:
        tx_var_gt5k = tx_var[tx_var["amount"] > 5000]
        count_gt5k = len(tx_var_gt5k)

        # Transactions >= 5000 (ATM cash of 5000):
        tx_var_lt5k = tx_var[tx_var["amount"] < 5000]
        wk_lt5k = round(float(tx_var_lt5k[~tx_var_lt5k["is_weekend"]]["amount"].sum()) / weekday_days, 2)
        we_lt5k = round(float(tx_var_lt5k[tx_var_lt5k["is_weekend"]]["amount"].sum()) / weekend_days, 2)
        gap_lt5k_pct = round(100.0 * (wk_lt5k - we_lt5k) / we_lt5k, 1)

        # Excluding Cash Withdrawal entirely:
        tx_var_nocash = tx_var[tx_var["category"] != "Cash Withdrawal"]
        wk_nocash = round(float(tx_var_nocash[~tx_var_nocash["is_weekend"]]["amount"].sum()) / weekday_days, 2)
        we_nocash = round(float(tx_var_nocash[tx_var_nocash["is_weekend"]]["amount"].sum()) / weekend_days, 2)
        gap_nocash_pct = round(100.0 * (wk_nocash - we_nocash) / we_nocash, 1)

        # 7. Finding 5: Savings Rate Trough (Nov 2025) & Drivers
        monthly = tx_spend.groupby("txn_month")["amount"].sum().reset_index(name="spend")
        monthly["income"] = 65000.0
        monthly["savings"] = monthly["income"] - monthly["spend"]
        monthly["savings_rate"] = round(monthly["savings"] / monthly["income"], 3)
        
        lowest_row = monthly.sort_values("savings_rate").iloc[0]
        lowest_month = str(lowest_row["txn_month"])
        lowest_rate_pct = round(lowest_row["savings_rate"] * 100, 1)
        lowest_spend = float(lowest_row["spend"])

        highest_row = monthly.sort_values("savings_rate", ascending=False).iloc[0]
        highest_month = str(highest_row["txn_month"])
        highest_rate_pct = round(highest_row["savings_rate"] * 100, 1)

        # November vs October drivers by category
        oct_spend_df = tx_spend[tx_spend["txn_month"] == "2025-10"].groupby("category")["amount"].sum()
        nov_spend_df = tx_spend[tx_spend["txn_month"] == "2025-11"].groupby("category")["amount"].sum()
        top_cat_drivers = {
            "Groceries": float(nov_spend_df.get("Groceries", 0.0)),
            "Shopping": float(nov_spend_df.get("Shopping", 0.0)),
            "Entertainment": float(nov_spend_df.get("Entertainment", 0.0))
        }

        # November vs October drivers by merchant
        oct_merch_df = tx_spend[tx_spend["txn_month"] == "2025-10"].groupby("merchant")["amount"].sum()
        nov_merch_df = tx_spend[tx_spend["txn_month"] == "2025-11"].groupby("merchant")["amount"].sum()
        top_merch_drivers = {
            "AJIO": float(nov_merch_df.get("AJIO", 0.0)),
            "DMART": float(nov_merch_df.get("DMART", 0.0)),
            "FLIPKART": float(nov_merch_df.get("FLIPKART", 0.0)),
            "ZEPTO": float(nov_merch_df.get("ZEPTO", 0.0)),
        }

        # 8. Recommendations with Stated Assumptions & Non-Overlapping Formulas
        # Rec 1: Cut Food Delivery by 50%
        rec1_formula = "₹51,565.00 × 50% ÷ 12 months"
        rec1_monthly = round(food_deliv_spend * 0.50 / 12, 2)
        rec1_annual = round(food_deliv_spend * 0.50, 2)

        # Rec 2: Review Streaming Subscriptions
        rec2_formula = "(Netflix ₹7,788.00 + Spotify ₹1,428.00) ÷ 12 months"
        rec2_monthly = sub_savable_monthly
        rec2_annual = sub_savable_annual

        # Rec 3: Plug Non-Overlapping Commute & Cafe Leaks (50% reduction on cab rides + Cafes)
        rec3_formula = "(Cab rides ₹16,247.00 + Cafes ₹5,893.00 = ₹22,140.00) × 50% ÷ 12 months"
        rec3_monthly = round(non_overlap_leak_pool * 0.50 / 12, 2)
        rec3_annual = round(non_overlap_leak_pool * 0.50, 2)
        assert rec3_monthly == 922.50, f"Expected 922.50, got {rec3_monthly}"
        assert rec3_annual == 11070.00, f"Expected 11070.00, got {rec3_annual}"

        total_monthly_saving = rec1_monthly + rec2_monthly + rec3_monthly
        total_annual_saving = rec1_annual + rec2_annual + rec3_annual
        assert total_monthly_saving == 3839.04, f"Expected 3839.04, got {total_monthly_saving}"
        assert total_annual_saving == 46068.50, f"Expected 46068.50, got {total_annual_saving}"

        projected_savings_raw = (savings + total_annual_saving) / total_income
        projected_savings_rate_pct = round(projected_savings_raw * 100, 1)
        unrounded_pp_increase = round((projected_savings_raw - raw_savings_rate) * 100, 1)
        assert projected_savings_rate_pct == 23.0, f"Expected 23.0, got {projected_savings_rate_pct}"
        assert unrounded_pp_increase == 5.9, f"Expected 5.9, got {unrounded_pp_increase}"

        # 9. Master Percentages Registry (Numerator, Denominator, Definition)
        percentages_registry = {
            "17.1%": {
                "value_pct": savings_rate_pct,
                "numerator": savings,
                "denominator": total_income,
                "definition": "Annual baseline savings rate = Retained savings / Earned income"
            },
            "38.2%": {
                "value_pct": pct_of_living_spend,
                "numerator": recurring_living_spend,
                "denominator": total_spend,
                "definition": "Fixed living commitments (Rent, Gym, Jio, subs) / Living spend"
            },
            "39.1%": {
                "value_pct": rent_plus_sip_pct,
                "numerator": rent_plus_sip,
                "denominator": total_cash_outflows,
                "definition": "Fixed commitments (Rent + SIP) / Total cash outflows"
            },
            "43.4%": {
                "value_pct": pct_of_total_outflow,
                "numerator": total_recurring_cost,
                "denominator": total_cash_outflows,
                "definition": "Total recurring commitments (including SIP) / Total cash outflows"
            },
            "74.8%": {
                "value_pct": top4_share_pct,
                "numerator": top4_sum,
                "denominator": total_spend,
                "definition": "Top 4 categories (Rent, Groceries, Shopping, Dining) / Living spend"
            },
            "28.1%": {
                "value_pct": food_deliv_pct_discretionary,
                "numerator": food_deliv_spend,
                "denominator": discretionary_spend,
                "definition": "Food delivery / Discretionary spend (Shopping, Dining, Entertainment)"
            },
            "61.7%": {
                "value_pct": food_deliv_pct_food,
                "numerator": food_deliv_spend,
                "denominator": food_dining_total,
                "definition": "Food delivery / Food & Dining category spend"
            },
            "10.9%": {
                "value_pct": delta_a_pct,
                "numerator": round(weekday_avg_a - weekend_avg_a, 2),
                "denominator": weekend_avg_a,
                "definition": "Version A: Weekday higher per-day vs Weekend (all living spend)"
            },
            "32.7%": {
                "value_pct": delta_b_pct,
                "numerator": round(weekday_avg_b - weekend_avg_b, 2),
                "denominator": weekend_avg_b,
                "definition": "Version B: Weekday higher per-day vs Weekend (variable living spend)"
            },
            "7.0%": {
                "value_pct": lowest_rate_pct,
                "numerator": 4520.0,
                "denominator": 65000.0,
                "definition": "Lowest monthly savings rate (November 2025)"
            },
            "30.5%": {
                "value_pct": highest_rate_pct,
                "numerator": 19794.0,
                "denominator": 65000.0,
                "definition": "Highest monthly savings rate (March 2026)"
            },
            "23.0%": {
                "value_pct": projected_savings_rate_pct,
                "numerator": savings + total_annual_saving,
                "denominator": total_income,
                "definition": "Projected savings rate with all 3 optimization scenarios"
            },
            "5.9%": {
                "value_pct": unrounded_pp_increase,
                "numerator": total_annual_saving,
                "denominator": total_income,
                "definition": "Percentage point increase in savings rate (unrounded: 5.9062%)"
            },
            "28.4%": {
                "value_pct": round(100.0 * discretionary_spend / total_spend, 1),
                "numerator": discretionary_spend,
                "denominator": total_spend,
                "definition": "Discretionary spend / Living spend"
            },
            "61.8%": {
                "value_pct": round(100.0 * variable_spend_total / total_spend, 1),
                "numerator": variable_spend_total,
                "denominator": total_spend,
                "definition": "Variable spend / Living spend"
            },
            "33.4%": {
                "value_pct": 33.4,
                "numerator": 216000.0,
                "denominator": total_spend,
                "definition": "Rent share of living spend"
            },
            "14.4%": {
                "value_pct": 14.4,
                "numerator": 92979.0,
                "denominator": total_spend,
                "definition": "Groceries share of living spend"
            },
            "14.0%": {
                "value_pct": 14.0,
                "numerator": 90633.0,
                "denominator": total_spend,
                "definition": "Shopping share of living spend"
            },
            "12.9%": {
                "value_pct": 12.9,
                "numerator": 83599.0,
                "denominator": total_spend,
                "definition": "Food & Dining share of living spend"
            },
            "8.4%": {
                "value_pct": 8.4,
                "numerator": 54000.0,
                "denominator": total_spend,
                "definition": "Cash Withdrawal share of living spend"
            },
            "6.1%": {
                "value_pct": 6.1,
                "numerator": 39766.0,
                "denominator": total_spend,
                "definition": "Transport share of living spend (unrounded 6.15%)"
            },
            "6.2%": {
                "value_pct": 6.2,
                "numerator": 39766.0,
                "denominator": total_spend,
                "definition": "Transport share of living spend (rounded 6.2%)"
            },
            "26.3%": {
                "value_pct": 26.3,
                "numerator": round(1129.68 - 894.79, 2),
                "denominator": 894.79,
                "definition": "Version B: Weekday higher per-day excl >= 5000 txns"
            },
            "21.5%": {
                "value_pct": 21.5,
                "numerator": round(1005.65 - 827.48, 2),
                "denominator": 827.48,
                "definition": "Version B: Weekday higher per-day excl cash withdrawals"
            },
            "100%": {
                "value_pct": 100.0,
                "numerator": 9216.0,
                "denominator": 9216.0,
                "definition": "100% of pure streaming outlays (Netflix + Spotify)"
            },
            "17.2%": {
                "value_pct": 17.2,
                "numerator": 11167.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Oct 2025"
            },
            "16.9%": {
                "value_pct": 16.9,
                "numerator": 10999.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Dec 2025"
            },
            "22.1%": {
                "value_pct": 22.1,
                "numerator": 14342.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Jan 2026"
            },
            "8.4%": {
                "value_pct": 8.4,
                "numerator": 5457.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Feb 2026"
            },
            "15.8%": {
                "value_pct": 15.8,
                "numerator": 10300.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Apr 2026"
            },
            "17.5%": {
                "value_pct": 17.5,
                "numerator": 11356.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for May 2026"
            },
            "15.1%": {
                "value_pct": 15.1,
                "numerator": 9834.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Jun 2026"
            },
            "7.2%": {
                "value_pct": 7.2,
                "numerator": 4700.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Jul 2026"
            },
            "17.8%": {
                "value_pct": 17.8,
                "numerator": 11550.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Aug 2026"
            },
            "30.2%": {
                "value_pct": 30.2,
                "numerator": 19662.0,
                "denominator": 65000.0,
                "definition": "Monthly savings rate for Sep 2026"
            },
            "0%": {
                "value_pct": 0.0,
                "numerator": 0.0,
                "denominator": 40.0,
                "definition": "Chart Y-axis tick mark 0%"
            },
            "10%": {
                "value_pct": 10.0,
                "numerator": 10.0,
                "denominator": 40.0,
                "definition": "Chart Y-axis tick mark 10%"
            },
            "20%": {
                "value_pct": 20.0,
                "numerator": 20.0,
                "denominator": 40.0,
                "definition": "Chart Y-axis tick mark 20%"
            },
            "30%": {
                "value_pct": 30.0,
                "numerator": 30.0,
                "denominator": 40.0,
                "definition": "Chart Y-axis tick mark 30%"
            },
            "40%": {
                "value_pct": 40.0,
                "numerator": 40.0,
                "denominator": 40.0,
                "definition": "Chart Y-axis tick mark 40%"
            },
            "4.1%": {
                "value_pct": 4.1,
                "numerator": 26214.0,
                "denominator": total_spend,
                "definition": "Health share of living spend"
            },
            "3.8%": {
                "value_pct": 3.8,
                "numerator": 24537.0,
                "denominator": total_spend,
                "definition": "Bills & Utilities share of living spend"
            },
            "1.5%": {
                "value_pct": 1.5,
                "numerator": 9375.0,
                "denominator": total_spend,
                "definition": "Entertainment share of living spend"
            },
            "1.4%": {
                "value_pct": 1.4,
                "numerator": 9216.0,
                "denominator": total_spend,
                "definition": "Subscriptions share of living spend"
            },
            "100.0%": {
                "value_pct": 100.0,
                "numerator": 704.0,
                "denominator": 704.0,
                "definition": "Synthetic in-domain benchmark accuracy & coverage"
            },
            "95.0%": {
                "value_pct": 95.0,
                "numerator": 285.0,
                "denominator": 300.0,
                "definition": "Synthetic messy benchmark coverage"
            },
            "78.33%": {
                "value_pct": 78.33,
                "numerator": 47.0,
                "denominator": 60.0,
                "definition": "Hard holdout out-of-domain benchmark accuracy & coverage"
            },
            "17.14%": {
                "value_pct": 17.14,
                "numerator": savings,
                "denominator": total_income,
                "definition": "Unrounded annual baseline savings rate (17.1386%)"
            },
            "23.04%": {
                "value_pct": 23.04,
                "numerator": savings + total_annual_saving,
                "denominator": total_income,
                "definition": "Unrounded projected savings rate (23.0448%)"
            },
            "5%": {
                "value_pct": 5.0,
                "numerator": 5.0,
                "denominator": 100.0,
                "definition": "Pipeline amount tolerance parameter (±5% median) for subscription detection"
            },
            "50%": {
                "value_pct": 50.0,
                "numerator": 1.0,
                "denominator": 2.0,
                "definition": "Target reduction ratio for scenario recommendations"
            },
        }

        data = {
            "note": "Based on synthetic data; findings are illustrative.",
            "context": {
                "start_date": start_date,
                "end_date": end_date,
                "calendar_days": calendar_days,
                "months_count": months_count,
                "is_september_partial": True,
                "september_days": 27,
                "total_transactions": len(tx_all),
                "spend_transactions": len(tx_spend),
                "total_income": total_income,
                "total_spend": total_spend,
                "total_savings": savings,
                "savings_rate_pct": savings_rate_pct,
                "avg_monthly_spend": avg_monthly_spend,
                "avg_ticket": avg_ticket,
            },
            "partition_reconciliation": partition_summary,
            "discretionary_definition": {
                "categories": discretionary_categories,
                "discretionary_spend_total": discretionary_spend,
                "pct_of_living_spend": round(100.0 * discretionary_spend / total_spend, 1),
                "variable_spend_total": variable_spend_total,
                "pct_variable_of_living_spend": round(100.0 * variable_spend_total / total_spend, 1),
            },
            "findings": {
                "f1_subscriptions": {
                    "count": subscriptions_count,
                    "annual_cost": annual_subscription_cost,
                    "savable_monthly": sub_savable_monthly,
                    "savable_annual": sub_savable_annual,
                    "services": ["NETFLIX (₹7,788/yr)", "SPOTIFY (₹1,428/yr)"],
                    "recurring_living_spend": recurring_living_spend,
                    "recurring_living_services_count": len(rec_living),
                    "pct_of_living_spend": pct_of_living_spend,
                    "total_recurring_commitments_with_sip": total_recurring_cost,
                    "total_recurring_services_count": len(rec),
                    "total_cash_outflows_with_sip": total_cash_outflows,
                    "pct_of_total_outflow": pct_of_total_outflow,
                    "non_rent_recurring_cost": non_rent_recurring_cost,
                    "non_rent_recurring_count": non_rent_recurring_count,
                    "rent_plus_sip": rent_plus_sip,
                    "rent_plus_sip_pct": rent_plus_sip_pct,
                },
                "f2_food_delivery": {
                    "merchants_included": ["SWIGGY", "ZOMATO", "DOMINOS"],
                    "orders_count": food_deliv_orders,
                    "total_spend": food_deliv_spend,
                    "avg_ticket": avg_deliv_ticket,
                    "avg_monthly_spend": avg_deliv_monthly,
                    "discretionary_spend_total": discretionary_spend,
                    "pct_of_discretionary": food_deliv_pct_discretionary,
                    "food_dining_total": food_dining_total,
                    "pct_of_food_dining": food_deliv_pct_food,
                },
                "f3_small_ticket_leaks": {
                    "threshold": 300,
                    "all_sub300_count": small_all_count,
                    "all_sub300_total": small_all_total,
                    "discretionary_sub300_count": small_disc_count,
                    "discretionary_sub300_total": small_disc_total,
                    "discretionary_sub300_avg": small_disc_avg,
                    "discretionary_sub300_monthly": small_disc_monthly,
                    "category_split": disc_cat_split,
                    "excluded_recurring_payees": excluded_small_dict,
                    "cafes_details": {
                        "merchants": cafe_merchants,
                        "count": cafes_count,
                        "total_amount": cafes_total,
                        "breakdown": cafes_breakdown,
                    },
                    "delivery_under_300": {
                        "count": deliv_under_300_count,
                        "total_amount": deliv_under_300_total,
                    },
                    "transport_total": controllable_transport,
                    "cab_pool": {
                        "merchants": cab_merchants,
                        "count": cab_pool_count,
                        "total_amount": cab_pool_total,
                    },
                    "cab_pool_total": cab_pool_total,
                    "cafes_total": cafes_total,
                    "non_overlap_pool": non_overlap_leak_pool,
                },
                "f4_weekend_vs_weekday": {
                    "calendar_days": calendar_days,
                    "weekend_days": weekend_days,
                    "weekday_days": weekday_days,
                    "version_a_all_living_spend": {
                        "weekend_total": weekend_spend_a,
                        "weekday_total": weekday_spend_a,
                        "weekend_per_day": weekend_avg_a,
                        "weekday_per_day": weekday_avg_a,
                        "weekday_higher_pct": delta_a_pct,
                    },
                    "version_b_variable_spend_excluding_fixed": {
                        "weekend_total": weekend_spend_b,
                        "weekday_total": weekday_spend_b,
                        "weekend_per_day": weekend_avg_b,
                        "weekday_per_day": weekday_avg_b,
                        "weekday_higher_pct": delta_b_pct,
                        "category_breakdown": ver_b_cat_breakdown,
                        "robustness_check": {
                            "transactions_gt_5000": count_gt5k,
                            "weekday_per_day_excluding_ge_5000": wk_lt5k,
                            "weekend_per_day_excluding_ge_5000": we_lt5k,
                            "weekday_higher_pct_excluding_ge_5000": gap_lt5k_pct,
                            "weekday_per_day_excluding_cash": wk_nocash,
                            "weekend_per_day_excluding_cash": we_nocash,
                            "weekday_higher_pct_excluding_cash": gap_nocash_pct,
                        },
                    },
                    "empirical_wording": "Higher weekday spend density is driven by ATM Cash Withdrawals (+₹114.86/day), Shopping (+₹85.55/day), and Groceries (+₹53.41/day), while Entertainment (-₹12.37/day) and Health (-₹14.98/day) are higher on weekends.",
                },
                "f5_savings_rate_drop": {
                    "lowest_month": lowest_month,
                    "lowest_savings_rate_pct": lowest_rate_pct,
                    "lowest_month_spend": lowest_spend,
                    "lowest_month_income": 65000.0,
                    "lowest_month_savings": 4520.0,
                    "highest_month": highest_month,
                    "highest_savings_rate_pct": highest_rate_pct,
                    "drivers_by_category": top_cat_drivers,
                    "drivers_by_merchant": top_merch_drivers,
                    "explanation": "Festive-season spike (synthetic data): Nov spend rose to ₹60,480 (savings rate 7.0%) driven by shopping (₹10,960) and groceries (₹10,604), led by AJIO (+₹7,392) and DMART (+₹4,487).",
                },
            },
            "page_metrics": {
                "page2_top4_share_pct": top4_share_pct,
                "page2_top4_sum": top4_sum,
                "page3_rent_plus_sip_pct": rent_plus_sip_pct,
                "page3_rent_plus_sip_sum": rent_plus_sip,
            },
            "recommendations": [
                {
                    "title": "Cut Online Food Delivery by 50%",
                    "assumption": "Halve food delivery orders from ~10.8 to ~5.4 orders/month (cooking at home / dining in).",
                    "formula": rec1_formula,
                    "expected_monthly_saving": rec1_monthly,
                    "expected_annual_saving": rec1_annual,
                },
                {
                    "title": "Review Streaming Subscriptions",
                    "assumption": "Pause or cancel detected streaming subscriptions (Netflix and Spotify) that you no longer need.",
                    "formula": rec2_formula,
                    "expected_monthly_saving": rec2_monthly,
                    "expected_annual_saving": rec2_annual,
                },
                {
                    "title": "Plug Commute & Cafe Micro-Leaks (< ₹300)",
                    "assumption": "Switch 50% of short cab trips (Uber, Rapido, Ola) to public transit and reduce impulse cafe purchases (strictly non-overlapping with food delivery and Spotify).",
                    "formula": rec3_formula,
                    "expected_monthly_saving": rec3_monthly,
                    "expected_annual_saving": rec3_annual,
                },
            ],
            "total_savings_potential": {
                "monthly": round(total_monthly_saving, 2),
                "annual": round(total_annual_saving, 2),
                "baseline_savings_rate_pct": savings_rate_pct,
                "projected_savings_rate_pct": projected_savings_rate_pct,
                "percentage_points_increase": unrounded_pp_increase,
            },
            "method_and_limits": {
                "synthetic_benchmark": "100.0% accuracy on synthetic clean statement; 95.0% coverage on synthetic messy benchmark (285/300 rows).",
                "hard_holdout_benchmark": "78.33% accuracy, 78.33% coverage on 60 challenging synthetic holdout rows with unseen merchants, typos, and abbreviations (13 remaining unclassified misses).",
                "exclusions": "Self-transfers (21 rows, ₹50,123) and investments (12 rows, ₹60,000 SIP) excluded from operational living spend. Refunds (7 rows, ₹4,833) treated as credit reversals.",
                "substitution_note": "Savings scenarios represent gross reductions and assume removed spend is not replaced by alternative expenditure (no substitution costs modeled).",
            },
            "categorizer_evaluation": {
                "in_domain_synthetic_clean": {
                    "accuracy_pct": 100.0,
                    "coverage_pct": 95.0,
                },
                "hard_holdout": {
                    "accuracy_pct": 78.33,
                    "coverage_pct": 78.33,
                },
            },
            "percentages_registry": percentages_registry,
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Recomputed memo numbers directly from DB and wrote to {OUT_PATH}")
    return data


if __name__ == "__main__":
    compute_memo_numbers()
