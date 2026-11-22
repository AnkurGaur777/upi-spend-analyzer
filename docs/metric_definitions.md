# Metric Definitions

### Spend
Debit transactions excluding transfers (is_transfer=1), reversals (is_reversal=1), and investments (category='Investments').
Reflects total operational and consumption outlays across all living expense categories (total: ₹6,46,319.00).

### Discretionary Spend
Expenditure in non-essential lifestyle categories: **Shopping** (₹90,633.00), **Food & Dining** (₹83,599.00), and **Entertainment** (₹9,375.00), totaling **₹1,83,607.00** (28.4% of total living spend).
*Note on distinction with Variable Spend:* Discretionary spend strictly comprises these 3 lifestyle categories. By contrast, **Variable Spend** refers to total living spend excluding fixed recurring commitments (Rent ₹2,16,000.00 and recurring bills ₹30,804.00), totaling **₹3,99,515.00** (61.8% of living spend).

### Food Delivery
Online food ordering transactions with merchants **SWIGGY**, **ZOMATO**, and **DOMINOS** within the Food & Dining category.
Total: 129 orders, ₹51,565.00 spend, average ticket ₹399.73. Represents 28.1% of discretionary spend and 61.7% of all Food & Dining spend.

### Income
Credit transactions categorized as 'Income' with is_transfer=0, representing primary earnings like salary.
Represents net external earned inflows into the account during each reporting period.

### Savings rate
Calculated as (Income - Spend) / NULLIF(Income, 0), rounded to three decimal places.
Measures the proportion of monthly earned income retained after consumption expenses.

### Transfers
Transactions moving funds between own accounts (SELF), family members, or peer-to-peer transfers.
Excluded from both spend and income to avoid artificial inflation of cash flow totals.

### Investments
Debit allocations towards capital assets and wealth creation, such as mutual fund SIPs and deposits.
Tracked independently from operational living spend to preserve accurate consumption analytics.

### Refunds
Credit entries originating from merchant returns or reversals flagged with is_refund=1.
Excluded from income and not netted against historical spend as a known baseline simplification.

### Cash withdrawals
ATM and branch cash disbursements flagged under the 'Cash Withdrawal' category.
Treated directly as spend at the time of withdrawal under the assumption that cash is consumed.

### Reversals
Transactions flagged with is_reversal=1 indicating failed, disputed, or technical rolled-back payments.
Neutralized and excluded from all spend and income metrics to prevent erroneous skewing.
