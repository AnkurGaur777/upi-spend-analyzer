# scripts/export_for_powerbi.py
import os
from pathlib import Path
import pandas as pd
from spend_analyzer.load import get_engine


def export_and_compute():
    out_dir = Path("powerbi/data")
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    with engine.connect() as conn:
        df_txns = pd.read_sql("SELECT * FROM transactions ORDER BY txn_date, txn_id", conn)
        df_rec = pd.read_sql("SELECT * FROM recurring_payments", conn)

    # 1. Assertions before writing
    assert len(df_txns) == 704, f"Expected 704 transactions, got {len(df_txns)}"
    assert len(df_rec) == 6, f"Expected 6 recurring payments, got {len(df_rec)}"

    # Format transactions columns
    df_txns["txn_date"] = pd.to_datetime(df_txns["txn_date"]).dt.strftime("%Y-%m-%d")
    for flag_col in ["is_transfer", "is_refund", "is_reversal"]:
        if flag_col in df_txns.columns:
            df_txns[flag_col] = df_txns[flag_col].fillna(0).astype(int)

    df_txns["amount"] = df_txns["amount"].map(lambda x: f"{float(x):.2f}")
    if "balance" in df_txns.columns:
        df_txns["balance"] = df_txns["balance"].map(lambda x: f"{float(x):.2f}" if pd.notnull(x) else "")

    txns_csv = out_dir / "transactions.csv"
    df_txns.to_csv(txns_csv, index=False, encoding="utf-8")

    # Format recurring_payments columns
    if "first_seen" in df_rec.columns:
        df_rec["first_seen"] = pd.to_datetime(df_rec["first_seen"]).dt.strftime("%Y-%m-%d")
    if "last_seen" in df_rec.columns:
        df_rec["last_seen"] = pd.to_datetime(df_rec["last_seen"]).dt.strftime("%Y-%m-%d")
    if "typical_amount" in df_rec.columns:
        df_rec["typical_amount"] = df_rec["typical_amount"].map(lambda x: f"{float(x):.2f}")
    if "annual_cost" in df_rec.columns:
        df_rec["annual_cost"] = df_rec["annual_cost"].map(lambda x: f"{float(x):.2f}")

    rec_csv = out_dir / "recurring_payments.csv"
    df_rec.to_csv(rec_csv, index=False, encoding="utf-8")

    # 2. Re-read exported CSV files to compute KPIs
    r_txns = pd.read_csv(txns_csv)
    r_rec = pd.read_csv(rec_csv)

    # Convert amounts back to float for computation
    r_txns["amount"] = r_txns["amount"].astype(float)
    r_rec["annual_cost"] = r_rec["annual_cost"].astype(float)

    # v_spend: debit, is_transfer=0, is_reversal=0, category != 'Investments'
    spend_mask = (
        (r_txns["direction"] == "debit")
        & (r_txns["is_transfer"] == 0)
        & (r_txns["is_reversal"] == 0)
        & (r_txns["category"] != "Investments")
    )
    df_spend = r_txns[spend_mask]

    # v_income: credit, category='Income', is_transfer=0
    income_mask = (
        (r_txns["direction"] == "credit")
        & (r_txns["category"] == "Income")
        & (r_txns["is_transfer"] == 0)
    )
    df_income = r_txns[income_mask]

    total_spend = df_spend["amount"].sum()
    total_income = df_income["amount"].sum()
    savings_rate = (total_income - total_spend) / total_income * 100.0

    months_in_data = r_txns["txn_month"].nunique()
    avg_monthly_spend = total_spend / months_in_data

    spend_rows_count = len(df_spend)
    avg_ticket = total_spend / spend_rows_count

    annual_sub_cost = r_rec[r_rec["category"] == "Subscriptions"]["annual_cost"].sum()
    total_annual_recurring = r_rec["annual_cost"].sum()

    # Monthly breakdown of spend
    monthly_spend = df_spend.groupby("txn_month")["amount"].sum()
    spend_2026_08 = monthly_spend.get("2026-08", 0.0)
    spend_2026_09 = monthly_spend.get("2026-09", 0.0)
    spend_mom_pct = ((spend_2026_09 - spend_2026_08) / spend_2026_08) * 100.0

    # 3M average for 2026-09 (2026-07, 2026-08, 2026-09)
    spend_2026_07 = monthly_spend.get("2026-07", 0.0)
    spend_3m_avg_2026_09 = (spend_2026_07 + spend_2026_08 + spend_2026_09) / 3.0

    # Monthly savings rate
    monthly_income = df_income.groupby("txn_month")["amount"].sum()
    # 2025-11
    inc_2025_11 = monthly_income.get("2025-11", 0.0)
    sp_2025_11 = monthly_spend.get("2025-11", 0.0)
    sr_2025_11 = ((inc_2025_11 - sp_2025_11) / inc_2025_11) * 100.0

    # 2026-03
    inc_2026_03 = monthly_income.get("2026-03", 0.0)
    sp_2026_03 = monthly_spend.get("2026-03", 0.0)
    sr_2026_03 = ((inc_2026_03 - sp_2026_03) / inc_2026_03) * 100.0

    # Category breakdown table
    cat_spend = df_spend.groupby("category")["amount"].sum().reset_index()
    cat_spend.columns = ["Category", "Spend (Rs)"]
    cat_spend["Share (%)"] = (cat_spend["Spend (Rs)"] / total_spend * 100.0).round(1)
    cat_spend = cat_spend.sort_values(by="Spend (Rs)", ascending=False).reset_index(drop=True)

    # Format Markdown
    md_lines = [
        "# Expected KPIs for Power BI",
        "",
        "## Overall Summary KPIs",
        "",
        "| KPI | Expected Value |",
        "| :--- | :--- |",
        f"| Total Spend | Rs {total_spend:,.2f} |",
        f"| Total Income | Rs {total_income:,.2f} |",
        f"| Savings Rate | {savings_rate:.1f}% |",
        f"| Months in Data | {months_in_data} |",
        f"| Avg Monthly Spend | Rs {avg_monthly_spend:,.2f} |",
        f"| Spend Rows Count | {spend_rows_count} |",
        f"| Avg Ticket | Rs {avg_ticket:,.2f} |",
        f"| Annual Subscription Cost | Rs {annual_sub_cost:,.2f} |",
        f"| Total Annual Recurring | Rs {total_annual_recurring:,.2f} |",
        f"| Total Spend (2026-08) | Rs {spend_2026_08:,.2f} |",
        f"| Total Spend (2026-09) | Rs {spend_2026_09:,.2f} |",
        f"| Spend MoM % (2026-09 vs 2026-08) | {spend_mom_pct:+.1f}% |",
        f"| Spend 3M Avg (2026-09) | Rs {spend_3m_avg_2026_09:,.2f} |",
        f"| Savings Rate (2025-11 - Lowest Month) | {sr_2025_11:.1f}% |",
        f"| Savings Rate (2026-03 - Highest Month) | {sr_2026_03:.1f}% |",
        "",
        "## Total Spend per Category",
        "",
        "| Category | Spend (Rs) | Share (%) |",
        "| :--- | :--- | :--- |",
    ]

    for _, row in cat_spend.iterrows():
        md_lines.append(f"| {row['Category']} | Rs {row['Spend (Rs)']:,.2f} | {row['Share (%)']:.1f}% |")

    kpi_md_path = Path("powerbi/expected_kpis.md")
    with open(kpi_md_path, "w", encoding="ascii") as f:
        f.write("\n".join(md_lines) + "\n")

    return kpi_md_path, txns_csv, rec_csv


if __name__ == "__main__":
    export_and_compute()
