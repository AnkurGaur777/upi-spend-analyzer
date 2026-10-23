-- sql/03_views.sql
-- MySQL 8 views for spend analysis

CREATE OR REPLACE VIEW v_spend AS
SELECT *
FROM transactions
WHERE direction = 'debit'
  AND is_transfer = 0
  AND is_reversal = 0
  AND category <> 'Investments';

CREATE OR REPLACE VIEW v_income AS
SELECT *
FROM transactions
WHERE direction = 'credit'
  AND category = 'Income'
  AND is_transfer = 0;

CREATE OR REPLACE VIEW v_monthly_summary AS
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
ORDER BY m.txn_month;
