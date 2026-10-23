-- sql/02_analysis_queries.sql
-- 
-- Definition of Spend:
-- Spend is defined by v_spend as all debit transactions excluding transfers, reversals, and investments:
--   direction = 'debit'
--   AND is_transfer = 0
--   AND is_reversal = 0
--   AND category <> 'Investments'
-- 

-- 1. Monthly income vs spend vs savings rate
SELECT txn_month, income, spend, savings_rate
FROM v_monthly_summary
ORDER BY txn_month;

-- 2. Spend by category with share of total
SELECT category,
       SUM(amount) AS spend,
       ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 1) AS pct_of_spend
FROM v_spend
GROUP BY category
ORDER BY spend DESC;

-- 3. Month-over-month change by category
WITH m AS (
  SELECT txn_month, category, SUM(amount) AS spend
  FROM v_spend
  GROUP BY txn_month, category
)
SELECT txn_month, category, spend,
       spend - LAG(spend) OVER (PARTITION BY category ORDER BY txn_month) AS change_vs_prev
FROM m
ORDER BY category, txn_month;

-- 4. Top 10 merchants
SELECT merchant,
       COUNT(*) AS txns,
       SUM(amount) AS spend,
       ROUND(AVG(amount), 0) AS avg_ticket
FROM v_spend
GROUP BY merchant
ORDER BY spend DESC
LIMIT 10;

-- 5. Weekday vs weekend spend
WITH RECURSIVE
bounds AS (
  SELECT MIN(txn_date) AS min_d, MAX(txn_date) AS max_d FROM transactions
),
calendar AS (
  SELECT min_d AS dt FROM bounds
  UNION ALL
  SELECT dt + INTERVAL 1 DAY FROM calendar, bounds WHERE dt < bounds.max_d
),
day_types AS (
  SELECT
    dt,
    CASE WHEN DAYOFWEEK(dt) IN (1, 7) THEN 'Weekend' ELSE 'Weekday' END AS day_type
  FROM calendar
),
daily_spends AS (
  SELECT txn_date AS dt, SUM(amount) AS daily_spend
  FROM v_spend
  GROUP BY txn_date
),
cal_spend AS (
  SELECT
    d.dt,
    d.day_type,
    COALESCE(s.daily_spend, 0.00) AS daily_spend
  FROM day_types d
  LEFT JOIN daily_spends s ON d.dt = s.dt
),
agg AS (
  SELECT
    day_type,
    COUNT(*) AS calendar_days,
    SUM(daily_spend) AS spend,
    ROUND(SUM(daily_spend) / COUNT(*), 2) AS avg_spend_per_day
  FROM cal_spend
  GROUP BY day_type
)
SELECT
  a.day_type,
  a.calendar_days,
  a.spend,
  a.avg_spend_per_day,
  CASE
    WHEN a.day_type = 'Weekend' THEN
      ROUND(100.0 * (a.avg_spend_per_day - w.avg_spend_per_day) / w.avg_spend_per_day, 1)
    ELSE NULL
  END AS pct_vs_weekday
FROM agg a
CROSS JOIN (SELECT avg_spend_per_day FROM agg WHERE day_type = 'Weekday') w
ORDER BY a.day_type DESC;

-- 6. "Small-ticket leak": many payments under Rs 300
SELECT category,
       COUNT(*) AS small_txns,
       SUM(amount) AS total
FROM v_spend
WHERE amount < 300
GROUP BY category
ORDER BY total DESC;

-- 7. Food delivery frequency per month
SELECT txn_month,
       COUNT(*) AS orders,
       SUM(amount) AS spend
FROM v_spend
WHERE merchant IN ('SWIGGY', 'ZOMATO', 'DOMINOS')
GROUP BY txn_month
ORDER BY txn_month;

-- 8. Subscriptions with annual cost
SELECT merchant, frequency, typical_amount, annual_cost
FROM recurring_payments
ORDER BY annual_cost DESC;

-- 8b. True subscriptions only
SELECT merchant, frequency, typical_amount, annual_cost
FROM recurring_payments
WHERE category = 'Subscriptions'
UNION ALL
SELECT 'TOTAL' AS merchant, NULL AS frequency, NULL AS typical_amount, SUM(annual_cost) AS annual_cost
FROM recurring_payments
WHERE category = 'Subscriptions';

-- 9. Rolling 3-month average spend
SELECT txn_month, spend,
       ROUND(AVG(spend) OVER (ORDER BY txn_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS rolling_3m
FROM (
  SELECT txn_month, SUM(amount) AS spend
  FROM v_spend
  GROUP BY txn_month
) t;

-- 10. Largest 10 single expenses (excluding rent/investments)
SELECT txn_date, merchant, category, amount
FROM v_spend
WHERE category NOT IN ('Rent', 'Investments')
ORDER BY amount DESC
LIMIT 10;

-- 11. Uncategorized rows to review (grow your rules from this)
-- Note: This query may legitimately return 0 rows when all spend is categorized.
SELECT merchant,
       COUNT(*) AS n,
       SUM(amount) AS total
FROM v_spend
WHERE category = 'Other'
GROUP BY merchant
ORDER BY n DESC
LIMIT 20;
