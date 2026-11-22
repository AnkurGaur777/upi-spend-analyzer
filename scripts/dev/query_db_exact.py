# scripts/query_db_exact.py
import sqlite3
import pandas as pd
from pathlib import Path
from spend_analyzer.load import get_engine
from sqlalchemy import text

def init_sqlite_views(conn):
    # Ensure standard views exist in SQLite
    conn.execute("DROP VIEW IF EXISTS v_spend")
    conn.execute("""
        CREATE VIEW v_spend AS
        SELECT * FROM transactions
        WHERE direction = 'debit'
          AND is_transfer = 0
          AND is_reversal = 0
          AND category <> 'Investments'
    """)
    conn.execute("DROP VIEW IF EXISTS v_income")
    conn.execute("""
        CREATE VIEW v_income AS
        SELECT * FROM transactions
        WHERE direction = 'credit'
          AND category = 'Income'
          AND is_transfer = 0
    """)
    conn.execute("DROP VIEW IF EXISTS v_monthly_summary")
    conn.execute("""
        CREATE VIEW v_monthly_summary AS
        WITH months AS (
          SELECT DISTINCT txn_month FROM transactions
        ),
        inc AS (
          SELECT txn_month, SUM(amount) AS income
          FROM v_income
          GROUP BY txn_month
        ),
        sp AS (
          SELECT txn_month, SUM(amount) AS spend
          FROM v_spend
          GROUP BY txn_month
        ),
        inv AS (
          SELECT txn_month, SUM(amount) AS investments
          FROM transactions
          WHERE direction = 'debit' AND category = 'Investments'
          GROUP BY txn_month
        )
        SELECT
          m.txn_month,
          COALESCE(inc.income, 0.00) AS income,
          COALESCE(sp.spend, 0.00) AS spend,
          (COALESCE(inc.income, 0.00) - COALESCE(sp.spend, 0.00)) AS savings,
          ROUND((COALESCE(inc.income, 0.00) - COALESCE(sp.spend, 0.00)) / NULLIF(COALESCE(inc.income, 0.00), 0), 3) AS savings_rate,
          COALESCE(inv.investments, 0.00) AS investments
        FROM months m
        LEFT JOIN inc ON m.txn_month = inc.txn_month
        LEFT JOIN sp  ON m.txn_month = sp.txn_month
        LEFT JOIN inv ON m.txn_month = inv.txn_month
        ORDER BY m.txn_month
    """)

def run():
    conn = sqlite3.connect("spend.db")
    init_sqlite_views(conn)
    
    print("="*60)
    print("1. ROW PARTITION (ALL 704 ROWS)")
    print("="*60)
    tx_all = pd.read_sql("SELECT * FROM transactions", conn)
    tx_spend = pd.read_sql("SELECT * FROM v_spend", conn)
    tx_income = pd.read_sql("SELECT * FROM v_income", conn)
    
    part_spend = len(tx_spend)
    part_income = len(tx_income)
    part_transfer = int((tx_all["is_transfer"] == 1).sum())
    part_refund = int(((tx_all["is_refund"] == 1) | (tx_all["is_reversal"] == 1)).sum())
    part_invest = int(((tx_all["direction"] == "debit") & (tx_all["category"] == "Investments")).sum())
    part_other = len(tx_all) - (part_spend + part_income + part_transfer + part_refund + part_invest)
    
    print(f"Total rows: {len(tx_all)}")
    print(f"Spend rows: {part_spend}")
    print(f"Income rows: {part_income}")
    print(f"Self-transfer rows: {part_transfer}")
    print(f"Refund/reversal rows: {part_refund}")
    print(f"Investment rows: {part_invest}")
    print(f"Other rows: {part_other}")
    print(f"Sum of parts: {part_spend + part_income + part_transfer + part_refund + part_invest + part_other}")
    assert part_spend + part_income + part_transfer + part_refund + part_invest + part_other == len(tx_all)
    
    print("\n" + "="*60)
    print("2. LIVING SPEND / INCOME / SAVINGS RATE")
    print("="*60)
    total_income = float(tx_income["amount"].sum())
    total_spend = float(tx_spend["amount"].sum())
    total_savings = total_income - total_spend
    savings_rate_raw = total_savings / total_income
    savings_rate_pct = round(savings_rate_raw * 100, 1)
    
    print(f"Total Income: Rs {total_income:,.2f}")
    print(f"Total Living Spend: Rs {total_spend:,.2f}")
    print(f"Total Retained Savings: Rs {total_savings:,.2f}")
    print(f"Savings Rate: {savings_rate_raw:.6f} ({savings_rate_pct}%)")
    
    print("\n" + "="*60)
    print("3. MONTHLY SPEND AND SAVINGS RATE FOR EVERY MONTH")
    print("="*60)
    m_summary = pd.read_sql("SELECT * FROM v_monthly_summary ORDER BY txn_month", conn)
    print(m_summary.to_string(index=False))
    
    print("\n" + "="*60)
    print("4. ALL CATEGORIES IN V_SPEND (TO DEFINE DISCRETIONARY)")
    print("="*60)
    cats = pd.read_sql("""
        SELECT category, COUNT(*) as txns, SUM(amount) as spend, 
               ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM v_spend), 2) as pct
        FROM v_spend
        GROUP BY category
        ORDER BY spend DESC
    """, conn)
    print(cats.to_string(index=False))
    
    print("\n" + "="*60)
    print("5. FOOD DELIVERY (SWIGGY, ZOMATO, DOMINOS)")
    print("="*60)
    food_deliv = pd.read_sql("""
        SELECT merchant, COUNT(*) as orders, SUM(amount) as spend,
               ROUND(AVG(amount), 2) as avg_ticket
        FROM v_spend
        WHERE merchant IN ('SWIGGY', 'ZOMATO', 'DOMINOS')
        GROUP BY merchant
        UNION ALL
        SELECT 'TOTAL' as merchant, COUNT(*) as orders, SUM(amount) as spend,
               ROUND(AVG(amount), 2) as avg_ticket
        FROM v_spend
        WHERE merchant IN ('SWIGGY', 'ZOMATO', 'DOMINOS')
    """, conn)
    print(food_deliv.to_string(index=False))
    
    print("\n" + "="*60)
    print("6. SUB-RS 300 COUNT / TOTAL / TOP CATEGORIES")
    print("="*60)
    sub300_cat = pd.read_sql("""
        SELECT category, COUNT(*) as txns, SUM(amount) as total,
               ROUND(AVG(amount), 2) as avg_ticket
        FROM v_spend
        WHERE amount < 300
        GROUP BY category
        ORDER BY total DESC
    """, conn)
    print(sub300_cat.to_string(index=False))
    sub300_tot = pd.read_sql("""
        SELECT COUNT(*) as count, SUM(amount) as total, ROUND(AVG(amount), 2) as avg_ticket
        FROM v_spend WHERE amount < 300
    """, conn)
    print("\nOverall sub-Rs 300:")
    print(sub300_tot.to_string(index=False))
    
    print("\n" + "="*60)
    print("7. WEEKDAY / WEEKEND (DAYS, SPEND, PER-DAY) - VERSION A & B")
    print("="*60)
    dates = pd.date_range("2025-10-01", "2026-09-27")
    weekend_days = int((dates.weekday >= 5).sum())
    weekday_days = int((dates.weekday < 5).sum())
    print(f"Total calendar days: {len(dates)} (Weekday: {weekday_days}, Weekend: {weekend_days})")
    
    # Version A: All living spend
    tx_spend["dt"] = pd.to_datetime(tx_spend["txn_date"])
    tx_spend["is_weekend"] = tx_spend["dt"].dt.weekday >= 5
    
    ver_a_wknd_spend = float(tx_spend[tx_spend["is_weekend"]]["amount"].sum())
    ver_a_wkday_spend = float(tx_spend[~tx_spend["is_weekend"]]["amount"].sum())
    ver_a_wknd_avg = ver_a_wknd_spend / weekend_days
    ver_a_wkday_avg = ver_a_wkday_spend / weekday_days
    delta_a_pct = 100.0 * (ver_a_wkday_avg - ver_a_wknd_avg) / ver_a_wknd_avg
    
    print(f"Version A (All living spend):")
    print(f"  Weekend: {weekend_days} days, Rs {ver_a_wknd_spend:,.2f}, Rs {ver_a_wknd_avg:,.2f}/day")
    print(f"  Weekday: {weekday_days} days, Rs {ver_a_wkday_spend:,.2f}, Rs {ver_a_wkday_avg:,.2f}/day")
    print(f"  Sum of spend: Rs {ver_a_wknd_spend + ver_a_wkday_spend:,.2f} (Total living spend: Rs {total_spend:,.2f})")
    print(f"  Weekday vs Weekend per-day difference: {delta_a_pct:+.2f}%")
    
    # Version B: Variable spend excluding Rent & fixed recurring bills
    rec = pd.read_sql("SELECT * FROM recurring_payments", conn)
    rec_living = rec[rec["category"] != "Investments"]
    rec_merchants = rec_living["merchant"].tolist()
    print(f"\nFixed recurring living merchants: {rec_merchants}")
    
    # Also explicitly exclude Rent if not in rec_merchants (though MR SHARMA HOUSE is Rent)
    tx_var = tx_spend[(~tx_spend["merchant"].isin(rec_merchants)) & (tx_spend["category"] != "Rent")]
    ver_b_wknd_spend = float(tx_var[tx_var["is_weekend"]]["amount"].sum())
    ver_b_wkday_spend = float(tx_var[~tx_var["is_weekend"]]["amount"].sum())
    ver_b_wknd_avg = ver_b_wknd_spend / weekend_days
    ver_b_wkday_avg = ver_b_wkday_spend / weekday_days
    delta_b_pct = 100.0 * (ver_b_wkday_avg - ver_b_wknd_avg) / ver_b_wknd_avg
    
    print(f"\nVersion B (Excluding Rent & Fixed Recurring Bills):")
    print(f"  Weekend: {weekend_days} days, Rs {ver_b_wknd_spend:,.2f}, Rs {ver_b_wknd_avg:,.2f}/day")
    print(f"  Weekday: {weekday_days} days, Rs {ver_b_wkday_spend:,.2f}, Rs {ver_b_wkday_avg:,.2f}/day")
    print(f"  Sum of spend: Rs {ver_b_wknd_spend + ver_b_wkday_spend:,.2f}")
    print(f"  Weekday vs Weekend per-day difference: {delta_b_pct:+.2f}%")
    
    print("\n" + "="*60)
    print("8. FIXED RECURRING COMMITMENTS")
    print("="*60)
    print(rec.to_string(index=False))
    
    print("\n" + "="*60)
    print("9. NOVEMBER VS OCTOBER DRIVERS BY CATEGORY AND MERCHANT")
    print("="*60)
    oct_nov_cat = pd.read_sql("""
        SELECT category,
               SUM(CASE WHEN txn_month = '2025-10' THEN amount ELSE 0 END) as oct_spend,
               SUM(CASE WHEN txn_month = '2025-11' THEN amount ELSE 0 END) as nov_spend,
               SUM(CASE WHEN txn_month = '2025-11' THEN amount ELSE 0 END) -
               SUM(CASE WHEN txn_month = '2025-10' THEN amount ELSE 0 END) as mom_change
        FROM v_spend
        WHERE txn_month IN ('2025-10', '2025-11')
        GROUP BY category
        ORDER BY mom_change DESC
    """, conn)
    print("Category MoM change (Nov vs Oct):")
    print(oct_nov_cat.to_string(index=False))
    
    oct_nov_merch = pd.read_sql("""
        SELECT merchant, category,
               SUM(CASE WHEN txn_month = '2025-10' THEN amount ELSE 0 END) as oct_spend,
               SUM(CASE WHEN txn_month = '2025-11' THEN amount ELSE 0 END) as nov_spend,
               SUM(CASE WHEN txn_month = '2025-11' THEN amount ELSE 0 END) -
               SUM(CASE WHEN txn_month = '2025-10' THEN amount ELSE 0 END) as mom_change
        FROM v_spend
        WHERE txn_month IN ('2025-10', '2025-11')
        GROUP BY merchant, category
        HAVING mom_change <> 0
        ORDER BY mom_change DESC
        LIMIT 15
    """, conn)
    print("\nTop Merchant MoM changes (Nov vs Oct):")
    print(oct_nov_merch.to_string(index=False))

if __name__ == "__main__":
    run()

