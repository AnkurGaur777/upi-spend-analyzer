# Power BI Dashboard Guide: Spend & Savings Analytics

This directory contains the interactive Power BI report file (`spend_dashboard.pbix`), data sources, expected KPI benchmarks, and dashboard visual previews.

---

## 1. File Structure

```
powerbi/
├── spend_dashboard.pbix          # Interactive Power BI report file
├── expected_kpis.md             # Benchmark KPIs verified against SQL views
├── README.md                    # Setup, refresh instructions, and DAX documentation
├── data/                        # Static CSV data exports for offline refresh
│   ├── transactions.csv         # Exported transactions table
│   └── recurring_payments.csv   # Exported recurring payments table
└── screenshots/                 # High-resolution (1080p) data-rendered previews
    ├── 01_overview.png
    ├── 02_where_it_goes.png
    ├── 03_leaks_subscriptions.png
    └── 04_insights.png
```

> **Note on Previews:** The images in `powerbi/screenshots/` are pixel-perfect **data-rendered dashboard previews** generated directly from the underlying database using `scripts/render_dashboard.py`. The `.pbix` file is the interactive version. If desired, you can replace the previews with direct exports from Power BI Desktop using the exact same filenames.

---

## 2. Opening & Refreshing the Dashboard

### Prerequisites
1. **Power BI Desktop** (Windows).
2. **Database Connection** (MySQL 8.0 on `localhost:3306` via Docker Compose, or static CSV fallback).
   > *Port Configuration Note:* If port 3306 is taken, set `MYSQL_PORT=3307` in `.env` and use the same port in `DATABASE_URL`.

### Steps to Refresh Data
1. **Open File**: Double-click `powerbi/spend_dashboard.pbix` to launch Power BI Desktop.
2. **Refresh via Database**:
   - Start the MySQL container: `docker compose up -d`
   - In Power BI Desktop, click **Home > Refresh**.
   - Power BI will query MySQL views (`v_spend`, `v_income`, `v_monthly_summary`) and tables.
3. **Alternative Refresh via Local CSVs**:
   - If MySQL is not running, go to **Home > Transform Data > Data Source Settings**.
   - Point the data source to the local CSV files in `powerbi/data/transactions.csv` and `powerbi/data/recurring_payments.csv`.
   - Click **Close & Apply**.

---

## 3. Data Model & Relationships

- **Fact Table**: `transactions` (many-to-one relationship with `DimDate` on `txn_date` -> `Date`)
- **Dimension Table**: `recurring_payments` (standalone dimension for subscription intelligence)
- **Calendar Table**: `DimDate` (calculated DAX table spanning the transaction date boundary)

### DimDate DAX Calculation
```dax
DimDate = ADDCOLUMNS(
    CALENDAR(MIN(transactions[txn_date]), MAX(transactions[txn_date])),
    "Year", YEAR([Date]),
    "Month No", MONTH([Date]),
    "Month", FORMAT([Date], "MMM YY"),
    "YearMonth", FORMAT([Date], "YYYY-MM")
)
```

---

## 4. DAX Measures Library

All metrics adhere strictly to the definitions documented in [`docs/metric_definitions.md`](file:///docs/metric_definitions.md).

### 1. Total Spend
Reflects operational living consumption, strictly excluding own-account transfers, reversals, and wealth-building investments:
```dax
Total Spend = 
CALCULATE(
    SUM(transactions[amount]),
    transactions[direction] = "debit",
    transactions[is_transfer] = 0,
    transactions[is_reversal] = 0,
    transactions[category] <> "Investments"
)
```

### 2. Total Income
Net earned income from employment inflows:
```dax
Total Income = 
CALCULATE(
    SUM(transactions[amount]),
    transactions[direction] = "credit",
    transactions[category] = "Income",
    transactions[is_transfer] = 0
)
```

### 3. Savings Rate %
Proportion of earned monthly salary retained after living expenditures:
```dax
Savings Rate = DIVIDE([Total Income] - [Total Spend], [Total Income], 0)
```

### 4. Spend LM (Last Month)
Spend in the preceding monthly period for MoM calculations:
```dax
Spend LM = CALCULATE([Total Spend], DATEADD(DimDate[Date], -1, MONTH))
```

### 5. Spend MoM %
Month-over-month percentage change in operational spending:
```dax
Spend MoM % = DIVIDE([Total Spend] - [Spend LM], [Spend LM], 0)
```

### 6. Avg Ticket
Average outlay per living debit transaction:
```dax
Avg Ticket = 
DIVIDE(
    [Total Spend],
    CALCULATE(
        COUNTROWS(transactions),
        transactions[direction] = "debit",
        transactions[is_transfer] = 0,
        transactions[is_reversal] = 0,
        transactions[category] <> "Investments"
    ),
    0
)
```

### 7. Annual Subscription Cost
Sum of annual costs for pure digital subscriptions (`category = 'Subscriptions'`):
```dax
Annual Subscription Cost = 
CALCULATE(
    SUM(recurring_payments[annual_cost]),
    recurring_payments[category] = "Subscriptions"
)
```

---

## 5. Technical Caveat: `Spend 3M Avg` vs. SQL Query 9

> [!IMPORTANT]
> **DAX vs. Relational SQL Implementation Difference:**
> In standard DAX, a naive rolling average using `DATESINPERIOD`:
> ```dax
> Spend 3M Avg (Date Level) = 
> AVERAGEX(
>     DATESINPERIOD(DimDate[Date], MAX(DimDate[Date]), -3, MONTH),
>     [Total Spend]
> )
> ```
> computes the average *per day* across the period.
> 
> To match **SQL Query 9** (which computes a rolling 3-month window average across monthly sums):
> ```sql
> -- SQL Query 9
> SELECT txn_month, spend,
>        ROUND(AVG(spend) OVER (ORDER BY txn_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS rolling_3m
> FROM (SELECT txn_month, SUM(amount) AS spend FROM v_spend GROUP BY txn_month) t;
> ```
> In DAX, you must average over distinct calendar months:
> ```dax
> Spend 3M Avg = 
> AVERAGEX(
>     DATESINPERIOD(DimDate[Date], MAX(DimDate[Date]), -3, MONTH),
>     CALCULATE([Total Spend], ALLEXCEPT(DimDate, DimDate[YearMonth]))
> )
> ```
> **Benchmark Verification:**
> In September 2026, the 3-month rolling window covers July (₹60,300), August (₹53,450), and September (₹45,338).
> `(60300 + 53450 + 45338) / 3 = ₹53,029.33` (exact match with SQL Query 9 and `expected_kpis.md`).

---

## 6. Report Pages Overview

1. **Page 1: Overview** – High-level cash flow KPIs, clustered column chart of monthly income vs. spend, secondary axis savings rate % line, and interactive month/category slicers.
2. **Page 2: Where It Goes** – Horizontal bar chart of spend across 10 categories, top 10 merchants table by total spend, and month-over-month category heat matrix.
3. **Page 3: Leaks & Subscriptions** – Automated subscription detection table, sub-₹300 small-ticket leak breakdown by category, and monthly food delivery order frequency.
4. **Page 4: Insights & Recommendations** – Executive findings with exact ₹ figures and 3 prioritized recommendations delivering ₹4,380/mo in savings.
