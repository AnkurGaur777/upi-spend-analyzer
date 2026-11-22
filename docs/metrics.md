# Pipeline Performance & Evaluation Metrics

This document records the measured metrics for the **UPI / Bank Statement Spend Analyzer** across parsing, cleaning, rule-based categorization, subscription detection, and idempotent database loading.

## 1. Pipeline Verification Summary (Section 7)

| Metric | Measurement / Method | Measured Value | Notes & Source |
| :--- | :--- | :--- | :--- |
| **Transactions Processed** | Total transactions parsed and deduplicated | **704 rows** | `statement_synthetic.csv` / `statement_icici_like.csv` (12 months: Oct 2025 – Sep 2026, 362 calendar days, Sept partial: 27 days) |
| **Bank Formats Supported** | Verified statement parser layouts | **2 formats** | `hdfc_like` (DD/MM/YY, separate debit/credit) & `icici_like` (DD-MM-YYYY, debit/credit), both passing tests |
| **Categorization Coverage** | % rows categorized into non-"Other" categories | **100.0%** (synthetic clean) / **95.0%** (synthetic messy) / **78.33%** (hard holdout) | 100% on clean statement; 95.0% (285/300) on synthetic messy benchmark; 78.33% (47/60) on untuned hard holdout |
| **Categorization Accuracy** | Correct classifications / Total evaluated | **100.0%** (synthetic clean) vs. **78.33%** (hard holdout) | Side-by-side comparison: 100% in-domain vs. 78.33% out-of-domain on challenging holdout set (47/60 correct, 13 unclassified) |
| **Pure Digital Subscriptions** | Rows in `recurring_payments` | **2 Subscriptions** (₹9,216.00 / yr) | Netflix (₹7,788/yr) + Spotify (₹1,428/yr). Savable: ₹768.00 / month |
| **Fixed Living Commitments (excl. SIP)**| Fixed recurring within living spend | **₹246,804.00 / yr** | **38.2% of living spend** (Rent ₹216k, Gym ₹18k, Jio ₹3.5k, pure subs ₹9.2k; denominator excludes SIP) |
| **Total Recurring Outflows (incl. SIP)**| Total recurring across all cash outflows | **₹306,804.00 / yr** | **43.4% of total cash outflows** (Living spend ₹646,319 + SIP ₹60,000 = ₹706,319 total outflows) |
| **Pipeline Runtime** | End-to-end execution time (~1,000 rows) | **0.32s** (1,000 rows) | Measured 1,000 parsed rows in 0.324s on SQLite (~2,880 rows/sec) |
| **Idempotent Loading** | Duplicate prevention verification | **0 duplicates inserted** | Second run with identical file yields `inserted=0`; database maintains exact 704 rows |

---

## 2. Mutually Exclusive Row Partition Reconciliation (Exact 704 Rows)

All 704 ingested rows partition cleanly into mutually exclusive financial classifications without overlap:

| Category / Type | Direction | Row Count | Total Amount (₹) | Definition & Accounting Rule |
| :--- | :--- | :---: | :---: | :--- |
| **Operational Living Spend** | Debit | **652** | ₹6,46,319.00 | Living expenses (`v_spend` view); excludes transfers, reversals, and investments |
| **Earned Income** | Credit | **12** | ₹7,80,000.00 | Monthly salary inflow (₹65,000.00 / month, `v_income` view) |
| **Self-Transfers** | Both | **21** | ₹50,123.00 | P2P wallet loads / self-account transfers (12 debits ₹38,000.00, 9 credits ₹12,123.00) |
| **Refunds / Reversals** | Credit | **7** | ₹4,833.00 | Reversals and merchant refunds (`is_reversal = 1`) |
| **Investments (SIP)** | Debit | **12** | ₹60,000.00 | HDFC Mutual Fund SIP (₹5,000.00 / mo capital accumulation; excluded from living spend) |
| **Other / Unclassified** | Either | **0** | ₹0.00 | Zero unclassified or orphaned rows |
| **TOTAL INGESTED** | — | **704** | — | **Exact match: 652 + 12 + 21 + 7 + 12 = 704** (asserted in `tests/test_pipeline.py`) |

---

## 3. Categorizer Evaluation: In-Domain vs. Hard Holdout

### A. Side-by-Side Benchmark Comparison
- **In-Domain Synthetic Clean (n=300)**: Accuracy = **100.00%**, Coverage = **95.00%** (285 categorized, 15 unclassified/other)
- **Out-of-Domain Hard Holdout (n=60)**: Accuracy = **78.33%**, Coverage = **78.33%** (47 categorized, 13 unclassified/other)
- **Why They Differ**: The 100% accuracy on synthetic clean data is expected because ground-truth labels originate from the same generator patterns, whereas the 78.33% accuracy on the 60-row hard holdout benchmarks true out-of-domain generalization against unseen regional merchants, abbreviations, and informal transfers.

### B. Hard Holdout Evaluation Before & After Amazon Rule Order Fix
- **Before Fix**: Accuracy = **76.67%** (46/60), Coverage = **78.33%** (47/60), 14 misses (1 active misclassification: `AMAZON PRIME` matched Shopping instead of Subscriptions).
- **After Rule-Order Fix (`AMAZON PRIME,Subscriptions,20`)**: Accuracy = **78.33%** (47/60), Coverage = **78.33%** (47/60), 13 misses (0 active misclassifications; all 13 are unclassified 'Other' fallbacks).

#### Known Limitations: Remaining 13 Unclassified Misses (n=13):
| Merchant | Raw Narration | Ground Truth | Predicted | Method | Root Cause / Limitation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| BLUE TOKAI | `UPI-BLUE TOKAI-bluetokai@yes-Coffee` | Food & Dining | Other | none | Unseen boutique specialty coffee brand |
| BLNKT | `UPI-BLNKT-blnkt@icici-Quick` | Groceries | Other | none | Vowel-stripped merchant abbreviation |
| UBR IND | `UPI-UBR IND-ubrind@paytm-Ride` | Transport | Other | none | Abbreviated Uber India billing entity |
| FLPKRT | `UPI-FLPKRT-flpkrt@axis-Order` | Shopping | Other | none | Truncated Flipkart merchant string |
| H&M ONLINE | `UPI-H&M ONLINE-hm@icici-Clothes` | Shopping | Other | none | Unseen apparel brand |
| AMZN | `UPI-AMZN-PAY-RETAIL ORDER` | Shopping | Other | none | Abbreviated Amazon retail token |
| BMS TICKETS | `BMS-TICKETS MOVIE SHOW` | Entertainment | Other | none | Truncated BookMyShow abbreviation |
| LANDLORD | `UPI-LANDLORD-RENT TRANSFER` | Rent | Other | none | Generic term without known landlord payee name |
| PAY TO 9876543210 | `UPI-PAY TO 9876543210-Split` | Transfers | Other | none | Phone number P2P string without personal name |
| SHARMAJI | `UPI-SHARMAJI-PAYMENT` | Transfers | Other | none | Informal Hindi moniker not in name dictionary |
| MOM | `UPI-MOM-GIFT TRANSFER` | Transfers | Other | none | Informal relative moniker |
| ROOMMATE | `UPI-ROOMMATE-FLAT EXPENSES` | Transfers | Other | none | Informal roommate reimbursement |
| CR FREELANCE DESIGN | `IMPS CR FREELANCE DESIGN CLIENT` | Income | Other | none | Non-standard freelance credit narration |

---

## 4. Database Telemetry & Idempotency Proof

### Database Engine Telemetry
- **Primary Database Engine**: MySQL 8.0 on `localhost:3306` (configured via `DATABASE_URL` in `docker-compose.yml`, `.env.example`, `load.py`, and `powerbi/README.md`)
- **Automated Fallback Engine**: SQLite (`sqlite:///spend.db`) with masked password console warning:
  `WARNING: MySQL at mysql+pymysql://spend:***@localhost:3306/spend_db is unreachable. Active Database: SQLite fallback ('sqlite:///spend.db')`

### Idempotent Insertion Proof
Fresh database execution test on both HDFC and ICICI formats (`scripts/verify_evidence.py`):
- **Run 1 (HDFC format, fresh DB)**: Processed 704 rows -> `inserted=704`, `duplicates_skipped=0`.
- **Run 2 (HDFC format, re-run)**: Processed 704 rows -> `inserted=0`, `duplicates_skipped=704`.
- **Run 1 (ICICI format, fresh DB)**: Processed 704 rows -> `inserted=704`, `duplicates_skipped=0`.
- **Run 2 (ICICI format, re-run)**: Processed 704 rows -> `inserted=0`, `duplicates_skipped=704`.
- **Exact deduplication key**: SHA-1 hash of `(txn_date, narration, amount, direction)`.

---

## 5. Hard Holdout Integrity & SHA256 Verification (Read-Only Separation)

To ensure scientific integrity and eliminate evaluation bias, generation and evaluation are decoupled:
- **Generation Script (`scripts/make_hard_holdout.py`)**: One-time generation of the adversarial holdout transactions and ground-truth references.
- **Evaluation Script (`scripts/evaluate_hard_holdout.py`)**: Strictly read-only evaluation that loads the pre-generated files and produces accuracy/coverage metrics without modifying file contents.
- **SHA256 Checksums (Normalized LF Checksums)**:
  - `data/raw/synthetic/statement_hard_holdout.csv`: `5683c77cec2631981423e11211491b066468054aa97dac5d03a568ee618eff3f`
  - `data/reference/labelled_holdout_hard.csv`: `b1cb5cfcc02793dbbdebcdd9f4256071e51ad65a838220a1af1f66756a55151b`
- **Integrity Test**: `tests/test_consistency.py::test_holdout_files_sha256_unmodified` validates that neither file is modified across test runs (normalized with `\r\n -> \n` for cross-platform Linux/Windows determinism).

---

## 6. MySQL Verification

A manual verification was run on MySQL 8 (Docker container, host port 3307):
- **Clean-volume load**: `inserted=704`, rerun `inserted=0` (0 duplicates inserted).
- **Core views**: `v_spend` = Rs 646,319.00 over 652 rows and `v_income` = Rs 780,000.00.
- **Analysis queries**: The 11 queries in `sql/02_analysis_queries.sql` produced output identical to `docs/sql_results.txt` (0 differences).
Earlier dashboard and memo numbers were generated on SQLite and match the MySQL results.
