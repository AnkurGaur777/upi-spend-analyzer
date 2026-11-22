# scripts/r5_analysis.py
import sqlite3
import pandas as pd

conn = sqlite3.connect("spend.db")

print("="*60)
print("1. RECURRING PAYMENTS")
print("="*60)
rec = pd.read_sql("SELECT * FROM recurring_payments", conn)
print(rec.to_string(index=False))

# Item 1: Rent + SIP
rent = float(rec[rec["category"] == "Rent"]["annual_cost"].sum())
sip = float(rec[rec["category"] == "Investments"]["annual_cost"].sum())
living_spend = 646319.0
total_outflow = living_spend + sip
print(f"\nRent: {rent}, SIP: {sip}, Rent+SIP: {rent+sip}")
print(f"Total Outflow (living {living_spend} + SIP {sip}): {total_outflow}")
print(f"Rent+SIP / Total Outflow: {(rent+sip)/total_outflow:.6f} -> {100.0*(rent+sip)/total_outflow:.1f}%")

# Item 1b: Page 2 74.7% vs 74.8%
cats = pd.read_sql("""
    SELECT category, SUM(amount) as spend
    FROM v_spend
    GROUP BY category
    ORDER BY spend DESC
""", conn)
top4_sum = cats.iloc[:4]["spend"].sum()
print(f"\nTop 4 categories: {cats.iloc[:4]['category'].tolist()}")
print(f"Top 4 sum: {top4_sum}")
print(f"Top 4 / Living Spend: {top4_sum/living_spend:.6f} -> {100.0*top4_sum/living_spend:.1f}% ({top4_sum} / {living_spend})")

print("\n" + "="*60)
print("2. DISCRETIONARY SMALL-TICKET LEAKS (< Rs 300 EXCLUDING RECURRING PAYEES)")
print("="*60)
# Item 4: Small-ticket leaks: define "discretionary small-ticket" as debits < Rs 300
# excluding detected recurring payees (Jio, Spotify, and anything in recurring_payments)
rec_merchants = rec["merchant"].tolist()
print(f"Recurring payees to exclude: {rec_merchants}")

# Let's inspect sub-300 debits with and without recurring payees
sub300_all = pd.read_sql("SELECT * FROM v_spend WHERE amount < 300", conn)
print(f"All sub-300 txns: {len(sub300_all)}, total: {sub300_all['amount'].sum()}")

# Exclude recurring payees
sub300_disc = pd.read_sql(f"""
    SELECT * FROM v_spend 
    WHERE amount < 300 
      AND merchant NOT IN ({','.join([repr(m) for m in rec_merchants])})
""", conn)

count_disc = len(sub300_disc)
total_disc = float(sub300_disc["amount"].sum())
avg_disc = float(sub300_disc["amount"].mean())
monthly_disc = total_disc / 12.0

print(f"\nDiscretionary sub-300 txns (excluding recurring payees):")
print(f"Count: {count_disc}")
print(f"Total: Rs {total_disc:,.2f}")
print(f"Average: Rs {avg_disc:,.2f}")
print(f"Monthly: Rs {monthly_disc:,.2f}")

# Category breakdown of discretionary sub-300
disc_by_cat = pd.read_sql(f"""
    SELECT category, COUNT(*) as txns, SUM(amount) as total, ROUND(AVG(amount), 2) as avg_ticket
    FROM v_spend
    WHERE amount < 300
      AND merchant NOT IN ({','.join([repr(m) for m in rec_merchants])})
    GROUP BY category
    ORDER BY total DESC
""", conn)
print("\nDiscretionary sub-300 by category:")
print(disc_by_cat.to_string(index=False))

# Also check what was excluded
excluded_sub300 = pd.read_sql(f"""
    SELECT merchant, category, COUNT(*) as txns, SUM(amount) as total
    FROM v_spend
    WHERE amount < 300
      AND merchant IN ({','.join([repr(m) for m in rec_merchants])})
    GROUP BY merchant, category
""", conn)
print("\nExcluded recurring sub-300 payees:")
print(excluded_sub300.to_string(index=False))

print("\n" + "="*60)
print("3. EXACT SQL/PANDAS AND MERCHANT LIST BEHIND 'CAFES RS 5,893'")
print("="*60)
# Sub-300, excluding Swiggy/Zomato/Dominos
# Let's see what is in Food & Dining < 300
sub300_food = pd.read_sql("""
    SELECT merchant, COUNT(*) as txns, SUM(amount) as total, ROUND(AVG(amount), 2) as avg_ticket
    FROM v_spend
    WHERE amount < 300 AND category = 'Food & Dining'
    GROUP BY merchant
    ORDER BY total DESC
""", conn)
print("All Food & Dining < 300:")
print(sub300_food.to_string(index=False))

# Cafes specifically
cafes_merchants = ["CAFE COFFEE DAY", "STARBUCKS"]
sub300_cafes = pd.read_sql(f"""
    SELECT merchant, COUNT(*) as txns, SUM(amount) as total, ROUND(AVG(amount), 2) as avg_ticket
    FROM v_spend
    WHERE amount < 300 
      AND category = 'Food & Dining'
      AND merchant IN ({','.join([repr(m) for m in cafes_merchants])})
    GROUP BY merchant
""", conn)
print("\nCafes < 300:")
print(sub300_cafes.to_string(index=False))
print(f"Total Cafes < 300: Rs {sub300_cafes['total'].sum():,.2f}")

# Food delivery < 300
food_deliv_merchants = ["SWIGGY", "ZOMATO", "DOMINOS"]
sub300_deliv = pd.read_sql(f"""
    SELECT merchant, COUNT(*) as txns, SUM(amount) as total, ROUND(AVG(amount), 2) as avg_ticket
    FROM v_spend
    WHERE amount < 300 
      AND category = 'Food & Dining'
      AND merchant IN ({','.join([repr(m) for m in food_deliv_merchants])})
    GROUP BY merchant
""", conn)
print("\nFood delivery < 300:")
print(sub300_deliv.to_string(index=False))
print(f"Total Food delivery < 300: Rs {sub300_deliv['total'].sum():,.2f}")

print("\n" + "="*60)
print("4. WEEKDAY VS WEEKEND: VERSION B BY CATEGORY (PER-DAY GAP)")
print("="*60)
# Version B variable spend: v_spend excluding recurring living payees (MR SHARMA HOUSE, CULT FIT, NETFLIX, JIO PREPAID, SPOTIFY)
# Total calendar days: 258 weekdays, 104 weekend days
dates = pd.date_range("2025-10-01", "2026-09-27")
weekend_days = int((dates.day_of_week >= 5).sum())
weekday_days = int((dates.day_of_week < 5).sum())

tx_var = pd.read_sql(f"""
    SELECT *, 
           CASE WHEN strftime('%w', txn_date) IN ('0', '6') THEN 'Weekend' ELSE 'Weekday' END as day_type
    FROM v_spend
    WHERE merchant NOT IN ({','.join([repr(m) for m in rec_merchants])})
""", conn)

cat_wk_summary = []
for cat in sorted(tx_var["category"].unique()):
    sub_cat = tx_var[tx_var["category"] == cat]
    wkday_spend = float(sub_cat[sub_cat["day_type"] == "Weekday"]["amount"].sum())
    wknd_spend = float(sub_cat[sub_cat["day_type"] == "Weekend"]["amount"].sum())
    wkday_per_day = wkday_spend / weekday_days
    wknd_per_day = wknd_spend / weekend_days
    per_day_gap = wkday_per_day - wknd_per_day
    gap_pct = 100.0 * per_day_gap / wknd_per_day if wknd_per_day > 0 else 0.0
    cat_wk_summary.append({
        "category": cat,
        "weekday_total": wkday_spend,
        "weekend_total": wknd_spend,
        "weekday_per_day": round(wkday_per_day, 2),
        "weekend_per_day": round(wknd_per_day, 2),
        "per_day_gap": round(per_day_gap, 2),
        "gap_pct": round(gap_pct, 1)
    })

cat_wk_df = pd.DataFrame(cat_wk_summary).sort_values("per_day_gap", ascending=False)
print("Version B Category Spend: Weekday vs Weekend (per-day):")
print(cat_wk_df.to_string(index=False))

print("\n" + "="*60)
print("5. ROBUSTNESS CHECK: VERSION B EXCLUDING TRANSACTIONS > RS 5,000")
print("="*60)
tx_var_le5k = tx_var[tx_var["amount"] <= 5000]
wkday_le5k = float(tx_var_le5k[tx_var_le5k["day_type"] == "Weekday"]["amount"].sum())
wknd_le5k = float(tx_var_le5k[tx_var_le5k["day_type"] == "Weekend"]["amount"].sum())
wkday_le5k_per_day = wkday_le5k / weekday_days
wknd_le5k_per_day = wknd_le5k / weekend_days
delta_le5k_pct = 100.0 * (wkday_le5k_per_day - wknd_le5k_per_day) / wknd_le5k_per_day

print("\nTop 10 transactions in tx_var by amount:")
print(tx_var.sort_values("amount", ascending=False)[["txn_date", "merchant", "category", "amount", "day_type"]].head(10).to_string(index=False))


print(f"\nVersion B (<= Rs 5,000):")
print(f"  Weekday: {weekday_days} days, Rs {wkday_le5k:,.2f}, Rs {wkday_le5k_per_day:,.2f}/day")
print(f"  Weekend: {weekend_days} days, Rs {wknd_le5k:,.2f}, Rs {wknd_le5k_per_day:,.2f}/day")
print(f"  Sum: Rs {wkday_le5k + wknd_le5k:,.2f}")
print(f"  Weekday vs Weekend per-day difference: {delta_le5k_pct:+.2f}%")
