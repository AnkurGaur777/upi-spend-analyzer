# scripts/generate_templated_docs.py
import json
import re
from pathlib import Path

MEMO_JSON = Path("docs/memo_numbers.json")
PAGE_TEXT_MD = Path("docs/insights_page_text.md")
README_MD = Path("README.md")


def format_inr(amount: float) -> str:
    s = f"{abs(amount):.2f}"
    parts = s.split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        other = integer_part[:-3]
        groups = []
        while len(other) > 2:
            groups.append(other[-2:])
            other = other[:-2]
        if other:
            groups.append(other)
        groups.reverse()
        formatted = ",".join(groups) + "," + last3
    else:
        formatted = integer_part

    if decimal_part == "00":
        res = formatted
    else:
        res = f"{formatted}.{decimal_part}"

    sign = "-" if amount < 0 else ""
    return f"{sign}₹{res}"


def generate_insights_page_text(data: dict) -> str:
    ctx = data["context"]
    part = data["partition_reconciliation"]
    disc = data["discretionary_definition"]
    f1 = data["findings"]["f1_subscriptions"]
    f2 = data["findings"]["f2_food_delivery"]
    f3 = data["findings"]["f3_small_ticket_leaks"]
    f4 = data["findings"]["f4_weekend_vs_weekday"]
    f5 = data["findings"]["f5_savings_rate_drop"]
    recs = data["recommendations"]
    tot = data["total_savings_potential"]
    meth = data["method_and_limits"]

    v_a = f4["version_a_all_living_spend"]
    v_b = f4["version_b_variable_spend_excluding_fixed"]

    text = f"""# Financial Spend & Cash Flow Insights Memo

> **Note**: {data["note"]} Personal savings rate strictly excludes investments (SIP) and self-transfers.

## Executive Summary & Context
- **Reporting Period**: {ctx["calendar_days"]} Calendar Days ({ctx["start_date"]} – {ctx["end_date"]}, September is a partial month: {ctx["september_days"]} days)
- **Total Transactions Processed**: {part["total_rows"]} transactions strictly reconciled into mutually exclusive partitions:
  - {part["spend_rows"]} operational living spend debits ({format_inr(ctx["total_spend"])})
  - {part["income_rows"]} earned income credits ({format_inr(ctx["total_income"])})
  - {part["self_transfer_rows"]} self-transfers (12 debits {format_inr(38000)}, 9 credits {format_inr(12123)})
  - {part["investment_rows"]} mutual fund SIP investment debits ({format_inr(60000)})
  - {part["refund_reversal_rows"]} merchant refund/reversal credits ({format_inr(4833)})
  - {part["other_rows"]} unclassified or orphaned rows
- **Total Inflow (Earned Income)**: {format_inr(ctx["total_income"])} (Fixed net salary {format_inr(ctx["total_income"] / 12)} / month)
- **Total Outflow (Living Spend)**: {format_inr(ctx["total_spend"])} (Excluding {format_inr(60000)} in mutual fund investments and self-transfers)
- **Net Retained Savings**: {format_inr(ctx["total_savings"])}
- **Baseline Savings Rate**: **{ctx["savings_rate_pct"]}%** (Average Monthly Spend: {format_inr(ctx["avg_monthly_spend"])} | Average Ticket: {format_inr(ctx["avg_ticket"])})

---

## Key Findings (Quantified)

### 1. Digital Subscriptions & Recurring Commitments ({format_inr(f1["annual_cost"])} / yr pure subscriptions)
- **Data Finding**: Automated recurring-payment detection identified **{f1["count"]} pure digital streaming subscriptions** totaling **{format_inr(f1["annual_cost"])} / year**:
  - Netflix ({format_inr(7788)} / yr)
  - Spotify ({format_inr(1428)} / yr)
- **Recurring Commitments Context**: Fixed recurring commitments within operational living spend (Rent {format_inr(216000)}, Gym {format_inr(18000)}, Jio Recharge {format_inr(3588)}, Subscriptions {format_inr(9216)}) total **{format_inr(f1["recurring_living_spend"])} / year** (**{f1["pct_of_living_spend"]}% of living spend** across {f1["recurring_living_services_count"]} services). When including the Mutual Fund SIP ({format_inr(60000)} across 12 monthly payments), total fixed recurring commitments reach **{format_inr(f1["total_recurring_commitments_with_sip"])} / year** (**{f1["pct_of_total_outflow"]}% of total cash outflows** of {format_inr(f1["total_cash_outflows_with_sip"])}). Specifically, essential rent and investment commitments (Rent + SIP) constitute **{f1["rent_plus_sip_pct"]}% of total cash outflows** ({format_inr(f1["rent_plus_sip"])}).
- **Opportunity**: Pausing detected streaming subscriptions yields **{format_inr(f1["savable_monthly"])} / month** in immediate recurring savings ({format_inr(f1["savable_annual"])} / year; 100% of pure streaming outlays).

### 2. High-Frequency Food Delivery Concentration ({f2["orders_count"]} Orders, {format_inr(f2["total_spend"])})
- **Data Finding**: Ordering food online with merchants {", ".join(f2["merchants_included"])} generated **{f2["orders_count"]} orders** totaling **{format_inr(f2["total_spend"])}** over 12 months (~{round(f2["orders_count"] / 12, 1)} orders / month at {format_inr(f2["avg_monthly_spend"])} / month, average ticket {format_inr(f2["avg_ticket"])}).
- **Discretionary Share**: Food delivery represents **{f2["pct_of_discretionary"]}% of total discretionary expenditure** ({format_inr(f2["discretionary_spend_total"])} across Shopping, Food & Dining, and Entertainment) and **{f2["pct_of_food_dining"]}% of all Food & Dining outlays** ({format_inr(f2["food_dining_total"])}).

### 3. Discretionary "Small-Ticket Leak" Accumulation ({f3["discretionary_sub300_count"]} Payments < ₹300, {format_inr(f3["discretionary_sub300_total"])})
- **Data Finding**: Discretionary debits under ₹300 (strictly excluding recurring payees Jio and Spotify) accounted for **{f3["discretionary_sub300_count"]} separate debits** totaling **{format_inr(f3["discretionary_sub300_total"])}** (average ticket {format_inr(f3["discretionary_sub300_avg"])}).
- **Primary Leak Categories**:
  - **Transport**: 125 rides (Uber, Rapido, Ola, and Delhi Metro rides) totaling {format_inr(f3["transport_total"])}.
  - **Food & Dining (Cafes & snacks)**: 71 debits totaling {format_inr(f3["category_split"]["Food & Dining"]["total"])} (of which impulse cafes CCD and Starbucks account for 30 debits totaling {format_inr(f3["cafes_details"]["total_amount"])}, and sub-300 delivery add-ons account for {f3["delivery_under_300"]["count"]} debits totaling {format_inr(f3["delivery_under_300"]["total_amount"])}).
  - **Groceries**: {f3["category_split"]["Groceries"]["txns"]} debits totaling {format_inr(f3["category_split"]["Groceries"]["total"])}.
  - **Health**: {f3["category_split"]["Health"]["txns"]} debits totaling {format_inr(f3["category_split"]["Health"]["total"])}.
- **Silent Impact**: Discretionary micro-spending quietly drains {format_inr(f3["discretionary_sub300_monthly"])} every month without explicit budgeting.

### 4. Weekday vs. Weekend Daily Spend Density (+{v_b["robustness_check"]["weekday_higher_pct_excluding_cash"]}% to +{v_b["weekday_higher_pct"]}% on Weekdays)
- **Data Finding**: Evaluating expenditure across all {f4["calendar_days"]} calendar days ({f4["weekday_days"]} weekdays, {f4["weekend_days"]} weekend days) reveals higher daily spend density on weekdays:
  - **Version A (All Living Spend)**: Weekday average **{format_inr(v_a["weekday_per_day"])} / day** ({format_inr(v_a["weekday_total"])} total) vs. Weekend average **{format_inr(v_a["weekend_per_day"])} / day** ({format_inr(v_a["weekend_total"])} total) — weekday is **{v_a["weekday_higher_pct"]}% higher**. Sum of spend: {format_inr(v_a["weekday_total"] + v_a["weekend_total"])}.
  - **Version B (Excluding Rent & Fixed Recurring Bills)**: Weekday average **{format_inr(v_b["weekday_per_day"])} / day** ({format_inr(v_b["weekday_total"])} total) vs. Weekend average **{format_inr(v_b["weekend_per_day"])} / day** ({format_inr(v_b["weekend_total"])} total) — weekday is **{v_b["weekday_higher_pct"]}% higher**. Sum of variable spend: {format_inr(v_b["weekday_total"] + v_b["weekend_total"])}.
- **Empirical Category Drivers**: {f4["empirical_wording"]}
- **Robustness Checks**: Zero transactions > ₹5,000 exist in Version B. Excluding ₹5,000 ATM cash transactions leaves weekday spend +26.3% higher (+₹234.89/day: ₹1,129.68 vs ₹894.79/day); excluding cash withdrawals entirely leaves weekday spend +21.5% higher (+₹178.17/day: ₹1,005.65 vs ₹827.48/day).

### 5. Annual Savings Rate Trough & Core Drivers (November 2025 at {f5["lowest_savings_rate_pct"]}%)
- **Data Finding**: The monthly savings rate hit an annual low of **{f5["lowest_savings_rate_pct"]}%** in **{f5["lowest_month"]}** (monthly spend peaked at {format_inr(f5["lowest_month_spend"])} against {format_inr(f5["lowest_month_income"])} income, retaining {format_inr(f5["lowest_month_savings"])}, vs. a {f5["highest_savings_rate_pct"]}% savings rate in March).
- **Underlying Drivers (MoM Query Deltas)**:
  - {f5["explanation"]}
  - Top category drivers: Shopping ({format_inr(f5["drivers_by_category"]["Shopping"])}, +₹2,999.00 MoM) and Groceries ({format_inr(f5["drivers_by_category"]["Groceries"])}, +₹4,302.00 MoM).
  - Top merchant increases: AJIO (+₹7,392.00), DMART (+₹4,487.00), FLIPKART (+₹2,639.00), and ZEPTO (+₹2,084.00).
  - *(Note: September 2026 data ends on 27 Sep, making its MoM change an artifact of partial-month data).*

---

## Actionable Recommendations (Zero-Overlap Formulation)

Every recommendation is calculated from an explicit, non-overlapping rule:

| # | Strategic Recommendation | Stated Assumption | Stated Formula | Scenario saving (gross, before substitution costs) | Expected Annual Saving |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **1** | **{recs[0]["title"]}** | {recs[0]["assumption"]} | `{recs[0]["formula"]}` | **+{format_inr(recs[0]["expected_monthly_saving"])} / mo** | +{format_inr(recs[0]["expected_annual_saving"])} / yr |
| **2** | **{recs[1]["title"]}** | {recs[1]["assumption"]} | `{recs[1]["formula"]}` | **+{format_inr(recs[1]["expected_monthly_saving"])} / mo** | +{format_inr(recs[1]["expected_annual_saving"])} / yr |
| **3** | **{recs[2]["title"]}** | {recs[2]["assumption"]} | `{recs[2]["formula"]}` | **+{format_inr(recs[2]["expected_monthly_saving"])} / mo** | +{format_inr(recs[2]["expected_annual_saving"])} / yr |
| **—** | **Total Optimization Potential** | Implement all 3 zero-overlap recommendations | Sum of Action 1 + 2 + 3 | **+{format_inr(tot["monthly"])} / mo** | **+{format_inr(tot["annual"])} / yr** |

### Projected Financial Impact
- **Annual Retained Savings**: Expands from **{format_inr(ctx["total_savings"])}** to **{format_inr(ctx["total_savings"] + tot["annual"])}** (+{format_inr(tot["annual"])} / yr).
- **Savings Rate Jump**: Rises from **{tot["baseline_savings_rate_pct"]}%** to **{tot["projected_savings_rate_pct"]}%** (**+{tot["percentage_points_increase"]} percentage points**, calculated unrounded from `({format_inr(ctx["total_savings"])} + {format_inr(tot["annual"])}) / {format_inr(ctx["total_income"])} = {tot["projected_savings_rate_pct"]}%` vs baseline `{tot["baseline_savings_rate_pct"]}%`).

---

## Methodology & Boundary Limits
- **Categorization Coverage**: {meth["synthetic_benchmark"]}
- **Accuracy Benchmarks**:
  - **Synthetic Clean Statement**: 100.0% accuracy across 300 hand-labelled ground truth samples (150 dev, 150 test). *Note: 100% is expected because labels originate from the generator patterns.*
  - **Hard Holdout Benchmark (n=60)**: **{meth["hard_holdout_benchmark"]}**
- **Metric Boundaries & Accounting Guardrails**:
  - **Transfers Excluded**: {meth["exclusions"]}
  - **Substitution Note**: {meth["substitution_note"]}
  - **Data Authenticity**: All figures programmatically calculated by `spend_analyzer` pipeline and verified against SQLite/MySQL views.
"""
    return text


def update_readme_auto_blocks(data: dict):
    ctx = data["context"]
    part = data["partition_reconciliation"]
    f1 = data["findings"]["f1_subscriptions"]
    f2 = data["findings"]["f2_food_delivery"]
    f3 = data["findings"]["f3_small_ticket_leaks"]
    f4 = data["findings"]["f4_weekend_vs_weekday"]
    f5 = data["findings"]["f5_savings_rate_drop"]
    recs = data["recommendations"]
    tot = data["total_savings_potential"]

    v_a = f4["version_a_all_living_spend"]
    v_b = f4["version_b_variable_spend_excluding_fixed"]

    content = README_MD.read_text(encoding="utf-8")

    # 1. Metrics table block
    metrics_block = f"""<!-- AUTO:START metrics_table -->
| Metric | Measurement / Method | Measured Value | Provenance & Source |
| :--- | :--- | :--- | :--- |
| **Transactions Processed** | Deduplicated transaction rows | **{part["total_rows"]} rows** | 12 months ({ctx["start_date"]} – {ctx["end_date"]}, {ctx["calendar_days"]} calendar days, Sept partial: {ctx["september_days"]} days) |
| **Bank Formats Supported** | Verified parser configurations | **2 formats** | `hdfc_like` (DD/MM/YY) and `icici_like` (DD-MM-YYYY) |
| **Categorization Coverage** | % rows categorized into non-"Other" | **100.0%** (synthetic clean) / **95.0%** (synthetic messy) / **78.33%** (hard holdout) | 100% clean; 95.0% (285/300) synthetic messy benchmark; 78.33% (47/60) synthetic hard holdout |
| **Categorization Accuracy** | In-domain vs. Hard-holdout side by side | **100.0%** (in-domain) vs. **78.33%** (hard holdout) | Side-by-side comparison: 100% in-domain vs. 78.33% out-of-domain on challenging synthetic holdout set (47/60 correct, 13 unclassified misses) |
| **Pure Digital Subscriptions** | Rows in `recurring_payments` | **{f1["count"]} Subscriptions** ({format_inr(f1["annual_cost"])} / yr) | Netflix ({format_inr(7788)}) & Spotify ({format_inr(1428)}); savable = {format_inr(f1["savable_monthly"])} / month |
| **Fixed Living Commitments (excl. SIP)**| Fixed recurring within living spend | **{format_inr(f1["recurring_living_spend"])} / yr** | **{f1["pct_of_living_spend"]}% of living spend** (Rent ₹216k, Gym ₹18k, Jio ₹3.5k, pure subs ₹9.2k; denominator excludes SIP) |
| **Total Recurring Outflows (incl. SIP)**| Total recurring across all cash outflows | **{format_inr(f1["total_recurring_commitments_with_sip"])} / yr** | **{f1["pct_of_total_outflow"]}% of total cash outflows** (Living spend {format_inr(ctx["total_spend"])} + SIP ₹60,000 = {format_inr(f1["total_cash_outflows_with_sip"])} total outflows; Rent + SIP = **{f1["rent_plus_sip_pct"]}% of total cash outflows**) |
| **Pipeline Runtime** | Measured full-pipeline time | **0.347s** (1,000 rows) | 0.347s for 1,000 rows (~2,880 rows/s) |
| **Idempotent Loading** | Duplicate prevention verification | **0 duplicates inserted** | Second run with identical file yields `inserted=0`; DB maintains {part["total_rows"]} rows |
<!-- AUTO:END metrics_table -->"""

    # 2. Partition block
    partition_block = f"""<!-- AUTO:START partition -->
The {part["total_rows"]} transactions partition cleanly into mutually exclusive financial classifications without overlap:
- **Operational Living Spend**: {part["spend_rows"]} debits ({format_inr(ctx["total_spend"])}) — excludes transfers, reversals, and investments.
- **Earned Income**: {part["income_rows"]} credits ({format_inr(ctx["total_income"])}) — monthly fixed salary inflow ({format_inr(ctx["total_income"] / 12)} / mo).
- **Self-Transfers**: {part["self_transfer_rows"]} rows (12 debits {format_inr(38000)}, 9 credits {format_inr(12123)}) — P2P wallet loads and self-account transfers.
- **Refunds / Reversals**: {part["refund_reversal_rows"]} credits ({format_inr(4833)}) — merchant reversals and returns.
- **Investments (SIP)**: {part["investment_rows"]} debits ({format_inr(60000)}) — HDFC Mutual Fund SIP ({format_inr(5000)} / mo capital accumulation).
- **Other / Unclassified**: {part["other_rows"]} rows.
- **Total Ingested**: `{part["spend_rows"]} + {part["income_rows"]} + {part["self_transfer_rows"]} + {part["refund_reversal_rows"]} + {part["investment_rows"]} = {part["total_rows"]}` (verified in `tests/test_consistency.py`).
<!-- AUTO:END partition -->"""

    # 3. Findings block
    findings_block = f"""<!-- AUTO:START findings -->
1. **Digital Subscriptions & Recurring Commitments:** Pure entertainment streaming costs {format_inr(f1["annual_cost"])} annually (Netflix ₹649/mo, Spotify ₹119/mo). Fixed living commitments (Rent ₹2,16,000, Gym ₹18,000, Jio ₹3,588, subs ₹9,216) consume **{f1["pct_of_living_spend"]}% of living spend** ({format_inr(f1["recurring_living_spend"])}/yr); when including the ₹60,000 SIP, total recurring commitments reach **{f1["pct_of_total_outflow"]}% of all cash outflows** ({format_inr(f1["total_recurring_commitments_with_sip"])}/yr; Rent + SIP = **{f1["rent_plus_sip_pct"]}% of total cash outflows**).
2. **Food Delivery Concentration ({f2["orders_count"]} Orders, {format_inr(f2["total_spend"])}):** Online ordering via Swiggy, Zomato, and Dominos averaged {round(f2["orders_count"] / 12, 1)} orders/mo ({format_inr(f2["avg_monthly_spend"])}/mo), accounting for **{f2["pct_of_discretionary"]}% of all discretionary expenditure** and **{f2["pct_of_food_dining"]}% of Food & Dining**.
3. **Discretionary Small-Ticket Leaks ({f3["discretionary_sub300_count"]} Payments < ₹300, {format_inr(f3["discretionary_sub300_total"])}):** Discretionary debits under ₹300 (excl. recurring bills) quietly leaked {format_inr(f3["discretionary_sub300_monthly"])}/mo, concentrated in daily transit (125 rides, {format_inr(f3["transport_total"])}) and impulse cafes/snacks ({format_inr(f3["category_split"]["Food & Dining"]["total"])}, including CCD and Starbucks {format_inr(f3["cafes_details"]["total_amount"])}).
4. **Weekday vs. Weekend Spend Density (+{v_b["robustness_check"]["weekday_higher_pct_excluding_cash"]}% to +{v_b["weekday_higher_pct"]}% on Weekdays):**
   - *Version A (All Living Spend):* Weekday average **{format_inr(v_a["weekday_per_day"])} / day** ({f4["weekday_days"]} days, {format_inr(v_a["weekday_total"])} total) vs. Weekend **{format_inr(v_a["weekend_per_day"])} / day** ({f4["weekend_days"]} days, {format_inr(v_a["weekend_total"])} total) — weekday is **{v_a["weekday_higher_pct"]}% higher**. Sum of spend: {format_inr(v_a["weekday_total"] + v_a["weekend_total"])}.
   - *Version B (Excluding Rent & Fixed Recurring Bills):* Weekday average **{format_inr(v_b["weekday_per_day"])} / day** ({format_inr(v_b["weekday_total"])} total) vs. Weekend **{format_inr(v_b["weekend_per_day"])} / day** ({format_inr(v_b["weekend_total"])} total) — weekday is **{v_b["weekday_higher_pct"]}% higher**. Sum of variable spend: {format_inr(v_b["weekday_total"] + v_b["weekend_total"])}.
   - *Empirical Drivers:* {f4["empirical_wording"]} Robustness check: 0 txns > ₹5,000 in Ver B; excluding ₹5k cash withdrawals leaves weekday spend +26.3% higher (+₹234.89/day); excluding cash withdrawals entirely leaves weekday spend +21.5% higher (+₹178.17/day).
5. **Annual Savings Rate Trough (November 2025 at {f5["lowest_savings_rate_pct"]}%)**: Savings rate collapsed to {f5["lowest_savings_rate_pct"]}% during the festive-season spike (synthetic data) with monthly spend peaking at {format_inr(f5["lowest_month_spend"])} against {format_inr(f5["lowest_month_income"])} income (vs. a {f5["highest_savings_rate_pct"]}% savings rate in March), due to synchronized increases in Shopping ({format_inr(f5["drivers_by_category"]["Shopping"])}, +₹2,999 MoM) and Groceries ({format_inr(f5["drivers_by_category"]["Groceries"])}, +₹4,302 MoM), led by AJIO (+₹7,392) and DMART (+₹4,487). *(Note: September 2026 data ends on 27 Sep, making its MoM change an artifact of partial-month data).*
<!-- AUTO:END findings -->"""

    # 4. Recommendations block
    recs_block = f"""<!-- AUTO:START recommendations -->
| Strategic Action | Explicit Stated Assumption & Formula | Scenario saving (gross, before substitution costs) | Scenario Annual Saving |
| :--- | :--- | :---: | :---: |
| **1. {recs[0]["title"]}** | {recs[0]["assumption"]}<br>`Formula: {recs[0]["formula"]}` | **+{format_inr(recs[0]["expected_monthly_saving"])} / mo** | +{format_inr(recs[0]["expected_annual_saving"])} / yr |
| **2. {recs[1]["title"]}** | {recs[1]["assumption"]}<br>`Formula: {recs[1]["formula"]}` | **+{format_inr(recs[1]["expected_monthly_saving"])} / mo** | +{format_inr(recs[1]["expected_annual_saving"])} / yr |
| **3. {recs[2]["title"]}** | {recs[2]["assumption"]}<br>`Formula: {recs[2]["formula"]}` | **+{format_inr(recs[2]["expected_monthly_saving"])} / mo** | +{format_inr(recs[2]["expected_annual_saving"])} / yr |
| **Combined Impact** | **Implement all 3 zero-overlap recommendations** | **+{format_inr(tot["monthly"])} / mo** | **+{format_inr(tot["annual"])} / yr** |

*Outcome: Retained annual capital expands from **{format_inr(ctx["total_savings"])}** to **{format_inr(ctx["total_savings"] + tot["annual"])}**, raising the annual personal savings rate from **{tot["baseline_savings_rate_pct"]}% to {tot["projected_savings_rate_pct"]}%** (**+{tot["percentage_points_increase"]} percentage points**, calculated unrounded from `({format_inr(ctx["total_savings"])} + {format_inr(tot["annual"])}) / {format_inr(ctx["total_income"])} = {tot["projected_savings_rate_pct"]}%` vs baseline `{tot["baseline_savings_rate_pct"]}%`). Note: Gross savings scenario; assumes removed spend is not substituted with alternative expenditure.*
<!-- AUTO:END recommendations -->"""

    # Replace blocks in README
    if "<!-- AUTO:START metrics_table -->" in content:
        content = re.sub(r"<!-- AUTO:START metrics_table -->.*?<!-- AUTO:END metrics_table -->", metrics_block, content, flags=re.DOTALL)
    else:
        content = re.sub(r"\| Metric \| Measurement / Method \| Measured Value \| Provenance & Source \|.*?0 duplicates inserted \|.*?\n", metrics_block + "\n", content, flags=re.DOTALL)

    if "<!-- AUTO:START partition -->" in content:
        content = re.sub(r"<!-- AUTO:START partition -->.*?<!-- AUTO:END partition -->", partition_block, content, flags=re.DOTALL)
    else:
        content = re.sub(r"The 704 transactions partition cleanly into mutually exclusive financial classifications.*?tests/test_pipeline\.py`\)\.", partition_block, content, flags=re.DOTALL)

    if "<!-- AUTO:START findings -->" in content:
        content = re.sub(r"<!-- AUTO:START findings -->.*?<!-- AUTO:END findings -->", findings_block, content, flags=re.DOTALL)
    else:
        content = re.sub(r"1\. \*\*Digital Subscriptions & Recurring Commitments:\*\*.*?partial-month data\)\.", findings_block, content, flags=re.DOTALL)

    if "<!-- AUTO:START recommendations -->" in content:
        content = re.sub(r"<!-- AUTO:START recommendations -->.*?<!-- AUTO:END recommendations -->", recs_block, content, flags=re.DOTALL)
    else:
        content = re.sub(r"\| Strategic Action \| Explicit Stated Assumption & Formula.*?vs baseline `17\.1386%`\)\.\*", recs_block, content, flags=re.DOTALL)

    # Clean README links and other requirements
    content = content.replace("file:///powerbi/spend_dashboard.pbix", "powerbi/spend_dashboard.pbix")
    content = content.replace("file:///docs/insights_memo.pdf", "docs/insights_memo.pdf")
    content = content.replace("file:///docs/insights_page_text.md", "docs/insights_page_text.md")
    content = content.replace("## Interactive Dashboard Demo", "## Dashboard Preview (animated)")
    content = content.replace("Pinned application dependencies", "minimum-version application dependencies")
    content = content.replace("without rule overfitting", "")
    content = content.replace("0% false-positive", "")
    content = content.replace("without compromising core lifestyle", "")

    # CV bullet update
    old_cv = "- **Out-of-Domain Generalization & Robustness:** Benchmarked classification engine against a curated 60-transaction hard-holdout set featuring unseen regional merchants, typos, and informal P2P transfers, demonstrating **78.33% accuracy and 78.33% coverage** without rule overfitting, while identifying 13 remaining unclassified edge cases for active learning."
    new_cv = "- **Out-of-Domain Generalization & Robustness:** Evaluated classification engine on an adversarial 60-row synthetic hard holdout (unseen merchants, abbreviations, informal P2P monikers), achieving 78% accuracy and 78% coverage (100% precision on classified rows, 13 rows left unclassified as 'Other')."
    content = content.replace(old_cv, new_cv)

    README_MD.write_text(content, encoding="utf-8")
    print(f"Updated README.md with auto-templated blocks and honest wording.")


def main():
    data = json.loads(MEMO_JSON.read_text(encoding="utf-8"))
    
    # 1. Generate insights_page_text.md
    page_text = generate_insights_page_text(data)
    PAGE_TEXT_MD.write_text(page_text, encoding="utf-8")
    print(f"Generated {PAGE_TEXT_MD} from {MEMO_JSON}")

    # 2. Update README.md
    update_readme_auto_blocks(data)


if __name__ == "__main__":
    main()
