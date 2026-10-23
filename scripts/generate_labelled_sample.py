# scripts/generate_labelled_sample.py
import random
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from spend_analyzer.parsers import parse_csv

random.seed(7)
START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 6, 30)
TOTAL_DAYS = (END_DATE - START_DATE).days

MESSY_CSV_PATH = Path("data/raw/synthetic/statement_messy.csv")
LABELS_CSV_PATH = Path("data/reference/labelled_sample.csv")


def random_date() -> date:
    return START_DATE + timedelta(days=random.randint(0, TOTAL_DAYS))


def ref() -> str:
    return "".join(random.choices("0123456789", k=12))


def upi(name: str, handle: str, note: str = "Payment") -> str:
    rand_icic = random.randint(100, 999)
    return f"UPI-{name.upper()}-{handle.lower().replace(' ', '')}@icici-ICIC0000{rand_icic}-{ref()}-{note}"


def card_swipe(name: str) -> str:
    last4 = "".join(random.choices("0123456789", k=4))
    return f"POS 416021XXXXXX{last4} {name.upper()} NEW DELHI"


def generate_samples():
    raw_items = []

    # 1. 30% EXACT known merchants (90 rows)
    KNOWN_MERCHANTS = [
        ("SWIGGY", "Food & Dining", (100, 650)),
        ("ZOMATO", "Food & Dining", (100, 650)),
        ("CAFE COFFEE DAY", "Food & Dining", (120, 500)),
        ("DOMINOS", "Food & Dining", (200, 750)),
        ("STARBUCKS", "Food & Dining", (250, 650)),
        ("BLINKIT", "Groceries", (150, 1200)),
        ("ZEPTO", "Groceries", (150, 1000)),
        ("BIGBASKET", "Groceries", (300, 2000)),
        ("DMART", "Groceries", (400, 2200)),
        ("UBER", "Transport", (50, 450)),
        ("OLA", "Transport", (50, 400)),
        ("RAPIDO", "Transport", (30, 220)),
        ("DELHI METRO", "Transport", (30, 80)),
        ("AMAZON", "Shopping", (300, 3500)),
        ("FLIPKART", "Shopping", (300, 3500)),
        ("MYNTRA", "Shopping", (400, 3000)),
        ("AJIO", "Shopping", (350, 2500)),
        ("NETFLIX", "Subscriptions", (199, 649)),
        ("SPOTIFY", "Subscriptions", (119, 299)),
        ("CULT FIT", "Health", (500, 1500)),
        ("TATA 1MG", "Health", (150, 1100)),
        ("BOOKMYSHOW", "Entertainment", (200, 800)),
        ("JIO PREPAID", "Bills & Utilities", (199, 699)),
        ("BSES", "Bills & Utilities", (1000, 2400)),
        ("HOUSE RENT", "Rent", (15000, 20000)),
    ]
    splits_known = ["dev"] * 45 + ["test"] * 45
    random.shuffle(splits_known)
    for sp in splits_known:
        m_name, m_cat, m_range = random.choice(KNOWN_MERCHANTS)
        amt = random.randint(m_range[0], m_range[1])
        if m_name == "HOUSE RENT":
            narr = f"NEFT DR-MR SHARMA-HOUSE RENT-{ref()}"
        elif m_name == "BSES":
            narr = f"BILLDESK-BSES RAJDHANI POWER-{ref()}"
        else:
            narr = upi(m_name, m_name)
        raw_items.append({
            "date": random_date(),
            "narration": narr,
            "amount": amt,
            "direction": "debit",
            "true_category": m_cat,
            "split": sp,
        })

    # 2. 25% VARIANTS/typos of known merchants (75 rows)
    VARIANTS = [
        ("SWIGY", "Food & Dining", (100, 650)),
        ("ZOMATTO", "Food & Dining", (100, 650)),
        ("STARBUCKS COFFEE", "Food & Dining", (250, 650)),
        ("DOMINOS PIZZA", "Food & Dining", (200, 750)),
        ("BLINK IT", "Groceries", (150, 1200)),
        ("BIG BASKET", "Groceries", (300, 2000)),
        ("DMART RETAIL", "Groceries", (400, 2200)),
        ("UBER INDIA", "Transport", (50, 450)),
        ("OLA CABS", "Transport", (50, 400)),
        ("RAPIDO BIKE", "Transport", (30, 220)),
        ("AMAZON PAY INDIA", "Shopping", (300, 3500)),
        ("FLIPKART INTERNET", "Shopping", (300, 3500)),
        ("NETFLIX COM", "Subscriptions", (199, 649)),
        ("SPOTIFY INDIA", "Subscriptions", (119, 299)),
        ("PVR CINEMAS", "Entertainment", (200, 800)),
        ("BOOKMYSHOW", "Entertainment", (200, 800)),
    ]
    splits_var = ["dev"] * 38 + ["test"] * 37
    random.shuffle(splits_var)
    for sp in splits_var:
        v_name, v_cat, v_range = random.choice(VARIANTS)
        amt = random.randint(v_range[0], v_range[1])
        narr = upi(v_name, v_name)
        raw_items.append({
            "date": random_date(),
            "narration": narr,
            "amount": amt,
            "direction": "debit",
            "true_category": v_cat,
            "split": sp,
        })

    # 3. 30% UNSEEN local shops (90 rows: 45 dev from DEV pool, 45 test from TEST pool)
    DEV_POOL = [
        ("SHARMA KIRANA STORE", "Groceries", (150, 1800)),
        ("GUPTA SWEETS", "Food & Dining", (80, 500)),
        ("SAI MEDICALS", "Health", (100, 1100)),
        ("CITY PETROL PUMP", "Transport", (100, 1500)),
        ("RAJU TEA STALL", "Food & Dining", (30, 200)),
        ("JAIN GENERAL STORE", "Groceries", (150, 1500)),
        ("NEW STAR RESTAURANT", "Food & Dining", (150, 750)),
        ("LIFELINE PHARMACY", "Health", (100, 900)),
        ("MODERN BOOK DEPOT", "Shopping", (100, 800)),
        ("METRO CAB SERVICE", "Transport", (80, 500)),
    ]
    TEST_POOL = [
        ("VERMA PROVISION STORE", "Groceries", (150, 1800)),
        ("BIKANERVALA", "Food & Dining", (100, 800)),
        ("HEALTH PLUS CHEMIST", "Health", (100, 1100)),
        ("HP FUEL STATION", "Transport", (100, 1500)),
        ("BABA DHABA", "Food & Dining", (80, 500)),
        ("PATEL SUPER MARKET", "Groceries", (150, 2000)),
        ("GOLDEN FAMILY RESTAURANT", "Food & Dining", (150, 850)),
        ("CITY CLINIC", "Health", (150, 950)),
        ("FASHION POINT", "Shopping", (300, 2500)),
        ("AUTO STAND DELHI", "Transport", (40, 300)),
    ]
    for _ in range(45):
        s_name, s_cat, s_range = random.choice(DEV_POOL)
        amt = random.randint(s_range[0], s_range[1])
        narr = card_swipe(s_name) if random.random() < 0.5 else upi(s_name, s_name)
        raw_items.append({
            "date": random_date(),
            "narration": narr,
            "amount": amt,
            "direction": "debit",
            "true_category": s_cat,
            "split": "dev",
        })
    for _ in range(45):
        s_name, s_cat, s_range = random.choice(TEST_POOL)
        amt = random.randint(s_range[0], s_range[1])
        narr = card_swipe(s_name) if random.random() < 0.5 else upi(s_name, s_name)
        raw_items.append({
            "date": random_date(),
            "narration": narr,
            "amount": amt,
            "direction": "debit",
            "true_category": s_cat,
            "split": "test",
        })

    # 4. 10% PERSON-TO-PERSON (30 rows: 15 dev, 15 test)
    P2P_NAMES = ["AMIT", "PRIYA", "ROHAN", "SNEHA", "VIKRAM", "KAVITA"]
    P2P_NOTES = ["Dinner split", "Thanks", "Rent share"]
    splits_p2p = ["dev"] * 15 + ["test"] * 15
    random.shuffle(splits_p2p)
    for sp in splits_p2p:
        p_name = random.choice(P2P_NAMES)
        p_note = random.choice(P2P_NOTES)
        # Mix of credits and debits; credits help maintain closing balance comfortably
        direction = "credit" if random.random() < 0.6 else "debit"
        amt = random.randint(1500, 3500) if direction == "credit" else random.randint(200, 1500)
        narr = upi(p_name, p_name, p_note)
        raw_items.append({
            "date": random_date(),
            "narration": narr,
            "amount": amt,
            "direction": direction,
            "true_category": "Transfers",
            "split": sp,
        })

    # 5. 5% UNKNOWABLE merchants (15 rows: 7 dev, 8 test)
    UNKNOWNS = ["M/S RK TRADERS", "XYZ ENTERPRISES", "ABC SERVICES", "GLOBAL VENTURES"]
    splits_unk = ["dev"] * 7 + ["test"] * 8
    random.shuffle(splits_unk)
    for sp in splits_unk:
        u_name = random.choice(UNKNOWNS)
        amt = random.randint(200, 3000)
        narr = card_swipe(u_name) if random.random() < 0.5 else upi(u_name, u_name)
        raw_items.append({
            "date": random_date(),
            "narration": narr,
            "amount": amt,
            "direction": "debit",
            "true_category": "Other",
            "split": sp,
        })

    assert len(raw_items) == 300, f"Expected 300 items, got {len(raw_items)}"

    # Sort strictly by date (stable)
    raw_items.sort(key=lambda x: x["date"])

    # Compute running balance starting at 60000.0
    balance = 60000.0
    out_statement = []
    labels = []

    for item in raw_items:
        amt = item["amount"]
        direction = item["direction"]
        if direction == "credit":
            balance += amt
        else:
            balance -= amt
        
        # In the unlikely event balance dips below 500, handle topup
        if balance < 500:
            topup = 30000
            balance += topup
            # Note: with our parameters balance stays well above 500

        out_statement.append({
            "Date": item["date"].strftime("%d/%m/%y"),
            "Narration": item["narration"],
            "Chq./Ref.No.": ref(),
            "Withdrawal Amt.": amt if direction == "debit" else "",
            "Deposit Amt.": amt if direction == "credit" else "",
            "Closing Balance": round(balance, 2),
        })

        labels.append({
            "true_category": item["true_category"],
            "split": item["split"],
        })

    assert len(out_statement) == 300

    # Write statement_messy.csv
    MESSY_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out_statement).to_csv(MESSY_CSV_PATH, index=False)
    print(f"Wrote {len(out_statement)} rows -> {MESSY_CSV_PATH}")

    # Parse with parse_csv to compute txn_id deterministically
    parsed_df = parse_csv(str(MESSY_CSV_PATH))
    assert len(parsed_df) == 300, f"Dropped rows in parse_csv: {len(parsed_df)} != 300"
    assert parsed_df["txn_id"].is_unique, "txn_id not unique in parsed statement"

    labels_df = pd.DataFrame(labels)
    labels_df.insert(0, "txn_id", parsed_df["txn_id"].values)

    LABELS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    labels_df.to_csv(LABELS_CSV_PATH, index=False)
    print(f"Wrote {len(labels_df)} rows -> {LABELS_CSV_PATH}")

    print("\nSplit counts:")
    print(labels_df["split"].value_counts())
    print("\nTrue category counts:")
    print(labels_df["true_category"].value_counts())


if __name__ == "__main__":
    generate_samples()
