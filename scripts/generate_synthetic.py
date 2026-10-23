# scripts/generate_synthetic.py
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)
START = date(2025, 10, 1)
N_MONTHS = 12
OUT = Path("data/raw/synthetic/statement_synthetic.csv")


def month_first(i: int) -> date:
    y = START.year + (START.month - 1 + i) // 12
    m = (START.month - 1 + i) % 12 + 1
    return date(y, m, 1)


def ref() -> str:
    return "".join(random.choices("0123456789", k=12))


def upi(name: str, handle: str, note: str = "Payment") -> str:
    return f"UPI-{name.upper()}-{handle}@icici-ICIC0000{random.randint(100, 999)}-{ref()}-{note}"


rows = []  # (date, narration, amount, direction)

for i in range(N_MONTHS):
    d0 = month_first(i)
    # --- fixed monthly items ---
    rows.append((d0 + timedelta(days=0), "NEFT CR-ACME TECH PVT LTD-SALARY", 65000, "credit"))
    rows.append((d0 + timedelta(days=4), "NEFT DR-MR SHARMA-HOUSE RENT", 18000, "debit"))
    rows.append((d0 + timedelta(days=2), upi("CULT FIT", "cultfit", "Gym"), 1500, "debit"))
    rows.append((d0 + timedelta(days=6), "ACH D- HDFC MUTUAL FUND-SIP", 5000, "debit"))
    rows.append((d0 + timedelta(days=11), upi("NETFLIX", "netflix", "Subscription"), 649, "debit"))
    rows.append((d0 + timedelta(days=14), upi("SPOTIFY", "spotify", "Subscription"), 119, "debit"))
    rows.append((d0 + timedelta(days=9), "BILLDESK-BSES RAJDHANI POWER", random.randint(1200, 2600), "debit"))
    rows.append((d0 + timedelta(days=17), upi("JIO PREPAID", "jio", "Recharge"), 299, "debit"))
    # --- variable spending ---
    for _ in range(random.randint(14, 22)):  # food delivery / cafes
        who = random.choice(["SWIGGY", "ZOMATO", "CAFE COFFEE DAY", "DOMINOS", "STARBUCKS"])
        rows.append((d0 + timedelta(days=random.randint(0, 27)), upi(who, who.lower().replace(" ", "")),
                     random.randint(120, 650), "debit"))
    for _ in range(random.randint(6, 10)):  # groceries
        who = random.choice(["BLINKIT", "ZEPTO", "BIGBASKET", "DMART"])
        rows.append((d0 + timedelta(days=random.randint(0, 27)), upi(who, who.lower()),
                     random.randint(200, 1800), "debit"))
    for _ in range(random.randint(10, 18)):  # transport
        who = random.choice(["UBER", "OLA", "RAPIDO", "DELHI METRO"])
        rows.append((d0 + timedelta(days=random.randint(0, 27)), upi(who, who.lower().replace(" ", "")),
                     random.randint(30, 420), "debit"))
    for _ in range(random.randint(2, 5)):  # shopping
        who = random.choice(["AMAZON", "FLIPKART", "MYNTRA", "AJIO"])
        rows.append((d0 + timedelta(days=random.randint(0, 27)), upi(who, who.lower()),
                     random.randint(300, 4500), "debit"))
    for _ in range(random.randint(0, 2)):  # health
        rows.append((d0 + timedelta(days=random.randint(0, 27)), upi("TATA 1MG", "1mg"),
                     random.randint(150, 1200), "debit"))
    for _ in range(random.randint(0, 2)):  # movies / entertainment
        rows.append((d0 + timedelta(days=random.randint(0, 27)), upi("BOOKMYSHOW", "bms"),
                     random.randint(250, 900), "debit"))
    for _ in range(random.randint(1, 3)):  # ATM cash
        rows.append((d0 + timedelta(days=random.randint(0, 27)), f"ATW-{random.randint(100000, 999999)}-NEW DELHI",
                     random.choice([1000, 2000, 3000, 5000]), "debit"))
    # self-transfer / family
    rows.append((d0 + timedelta(days=random.randint(18, 25)), upi("PAPA", "papa", "Family"),
                 random.choice([2000, 3000, 5000]), "debit"))
    # occasional refund + friend reimbursement
    if random.random() < 0.5:
        rows.append((d0 + timedelta(days=random.randint(5, 25)), upi("AMAZON REFUND", "amazon", "Refund"),
                     random.randint(300, 1500), "credit"))
    if random.random() < 0.7:
        rows.append((d0 + timedelta(days=random.randint(5, 25)), upi("RAHUL", "rahul", "Dinner split"),
                     random.randint(300, 1200), "credit"))

df = pd.DataFrame(rows, columns=["date", "narration", "amount", "direction"]).sort_values("date", kind="stable")

balance = 40000.0
out = []
for r in df.itertuples():
    balance += r.amount if r.direction == "credit" else -r.amount
    if balance < 500:  # keep the account from going negative: top-up credit
        topup = 20000
        balance += topup
        out.append({"Date": r.date.strftime("%d/%m/%y"), "Narration": "NEFT CR-SELF-TOPUP", "Chq./Ref.No.": ref(),
                    "Withdrawal Amt.": "", "Deposit Amt.": topup, "Closing Balance": round(balance, 2)})
    out.append({
        "Date": r.date.strftime("%d/%m/%y"),
        "Narration": r.narration,
        "Chq./Ref.No.": ref(),
        "Withdrawal Amt.": r.amount if r.direction == "debit" else "",
        "Deposit Amt.": r.amount if r.direction == "credit" else "",
        "Closing Balance": round(balance, 2),
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(out).to_csv(OUT, index=False)
print(f"Wrote {len(out)} rows -> {OUT}")
