# scripts/print_round5_evidence.py
import sqlite3
import pandas as pd

conn = sqlite3.connect("spend.db")

print("=== ITEM 4: DISCRETIONARY SMALL-TICKET DEBITS (< Rs 300, EXCLUDING JIO & SPOTIFY) ===")
q4 = """
SELECT 
    category,
    COUNT(*) AS txns,
    ROUND(SUM(amount), 2) AS total_amount,
    ROUND(AVG(amount), 2) AS avg_ticket
FROM transactions
WHERE direction = 'debit'
  AND is_transfer = 0
  AND is_reversal = 0
  AND category <> 'Investments'
  AND amount < 300
  AND merchant NOT IN ('JIO PREPAID', 'SPOTIFY')
GROUP BY category
ORDER BY total_amount DESC;
"""
df4 = pd.read_sql(q4, conn)
print(df4.to_string(index=False))
print(f"Total Discretionary Sub-300: {df4['txns'].sum()} transactions, Rs {df4['total_amount'].sum():.2f}")

print("\n=== ITEM 5: CAFES (< Rs 300, NON-OVERLAPPING WITH FOOD DELIVERY) ===")
q5 = """
SELECT 
    merchant,
    COUNT(*) AS txns,
    ROUND(SUM(amount), 2) AS total_amount,
    ROUND(AVG(amount), 2) AS avg_ticket
FROM transactions
WHERE direction = 'debit'
  AND is_transfer = 0
  AND is_reversal = 0
  AND merchant IN ('CAFE COFFEE DAY', 'STARBUCKS')
  AND amount < 300
GROUP BY merchant
ORDER BY total_amount DESC;
"""
df5 = pd.read_sql(q5, conn)
print(df5.to_string(index=False))
print(f"Total Cafes Sub-300: {df5['txns'].sum()} transactions, Rs {df5['total_amount'].sum():.2f}")

print("\n=== ITEM 7: WEEKDAY VS WEEKEND VERSION B SPEND BY CATEGORY (PER-DAY) ===")
q7 = """
WITH base AS (
    SELECT 
        category,
        amount,
        CASE strftime('%w', txn_date)
            WHEN '0' THEN 'Weekend'
            WHEN '6' THEN 'Weekend'
            ELSE 'Weekday'
        END AS day_type
    FROM transactions
    WHERE direction = 'debit'
      AND is_transfer = 0
      AND is_reversal = 0
      AND category <> 'Investments'
      AND NOT (merchant = 'MR SHARMA HOUSE' AND category = 'Rent')
      AND NOT (merchant = 'CULT FIT' AND category = 'Health')
      AND NOT (merchant = 'JIO PREPAID' AND category = 'Bills & Utilities')
      AND NOT (category = 'Subscriptions')
)
SELECT 
    category,
    ROUND(SUM(CASE WHEN day_type = 'Weekday' THEN amount ELSE 0 END), 2) AS weekday_spend,
    ROUND(SUM(CASE WHEN day_type = 'Weekend' THEN amount ELSE 0 END), 2) AS weekend_spend,
    ROUND(SUM(CASE WHEN day_type = 'Weekday' THEN amount ELSE 0 END) / 258.0, 2) AS weekday_per_day,
    ROUND(SUM(CASE WHEN day_type = 'Weekend' THEN amount ELSE 0 END) / 104.0, 2) AS weekend_per_day,
    ROUND((SUM(CASE WHEN day_type = 'Weekday' THEN amount ELSE 0 END) / 258.0) - (SUM(CASE WHEN day_type = 'Weekend' THEN amount ELSE 0 END) / 104.0), 2) AS per_day_gap
FROM base
GROUP BY category
ORDER BY per_day_gap DESC;
"""
df7 = pd.read_sql(q7, conn)
print(df7.to_string(index=False))

print("\n=== ITEM 7 ROBUSTNESS CHECKS ===")
q_gt5k = """
SELECT COUNT(*) AS txns_gt_5000 
FROM transactions
WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND category <> 'Investments'
  AND NOT (merchant = 'MR SHARMA HOUSE' AND category = 'Rent')
  AND NOT (merchant = 'CULT FIT' AND category = 'Health')
  AND NOT (merchant = 'JIO PREPAID' AND category = 'Bills & Utilities')
  AND NOT (category = 'Subscriptions')
  AND amount > 5000;
"""
print("Transactions > Rs 5,000 in Version B:", pd.read_sql(q_gt5k, conn).iloc[0, 0])

q_atm5k = """
SELECT COUNT(*) AS atm_5000_txns, SUM(amount) AS atm_5000_total
FROM transactions
WHERE direction = 'debit' AND merchant = 'ATM CASH' AND amount = 5000;
"""
df_atm = pd.read_sql(q_atm5k, conn)
print(f"ATM Cash transactions of exactly Rs 5,000: {df_atm.iloc[0, 0]} txns, total Rs {df_atm.iloc[0, 1]:.2f}")

