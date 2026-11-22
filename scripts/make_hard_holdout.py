# scripts/make_hard_holdout.py
"""Generate synthetic hard holdout benchmark dataset.

Run once to generate data/raw/synthetic/statement_hard_holdout.csv
and data/reference/labelled_holdout_hard.csv.
"""
from pathlib import Path
import pandas as pd

from spend_analyzer.parsers import make_txn_id

RAW_CSV = Path("data/raw/synthetic/statement_hard_holdout.csv")
LABELS_CSV = Path("data/reference/labelled_holdout_hard.csv")

# 60 Realistic Hard Holdout Transactions
# (Date DD/MM/YY, Narration, Withdrawal, Deposit, Balance, True Category)
HARD_SAMPLES = [
    # Food & Dining (Typos, regional chains, abbreviations)
    ("05/01/26", "UPI-SWGGY-swggy@icici-112233445566-Food", "450", "", "50000.0", "Food & Dining"),
    ("06/01/26", "UPI-ZOMTO-zomto@hdfc-223344556677-Lunch", "320", "", "49680.0", "Food & Dining"),
    ("07/01/26", "UPI-CHAAYOS-chaayos@icici-334455667788-Tea", "180", "", "49500.0", "Food & Dining"),
    ("08/01/26", "UPI-HALDIRAM-haldiram@axis-445566778899-Dinner", "850", "", "48650.0", "Food & Dining"),
    ("09/01/26", "UPI-BLUE TOKAI-bluetokai@yes-556677889900-Coffee", "260", "", "48390.0", "Food & Dining"),
    ("10/01/26", "UPI-BARBEQUE NATION-bbqn@icici-667788990011-Dinner", "1800", "", "46590.0", "Food & Dining"),
    ("11/01/26", "POS-CHAI POINT POS NEW DELHI", "140", "", "46450.0", "Food & Dining"),
    ("12/01/26", "UPI-MCDONALDS-mcd@hdfc-778899001122-Burger", "399", "", "46051.0", "Food & Dining"),
    ("13/01/26", "UPI-BURGER KING-bk@icici-889900112233-Food", "299", "", "45752.0", "Food & Dining"),
    ("14/01/26", "UPI-SUBWAY-subway@sbi-990011223344-Sub", "240", "", "45512.0", "Food & Dining"),

    # Groceries (Local kirana, hypermarket, typo)
    ("15/01/26", "UPI-BLNKT-blnkt@icici-102938475610-Quick", "420", "", "45092.0", "Groceries"),
    ("16/01/26", "UPI-LULU HYPERMARKET-lulu@kotak-203948576102-Grocery", "2450", "", "42642.0", "Groceries"),
    ("17/01/26", "POS-40192-KIRANA GENERAL STORE", "680", "", "41962.0", "Groceries"),
    ("18/01/26", "UPI-NATURE BASKET-nb@axis-304958671203-Veggies", "890", "", "41072.0", "Groceries"),
    ("19/01/26", "UPI-SPENCERS RETAIL-spencers@icici-405968712304-Store", "1250", "", "39822.0", "Groceries"),

    # Transport (Airlines, train, petrol pumps, typos)
    ("20/01/26", "UPI-UBR IND-ubrind@paytm-506978823405-Ride", "340", "", "39482.0", "Transport"),
    ("21/01/26", "UPI-RAPDO-rapdo@icici-607989934506-Auto", "120", "", "39362.0", "Transport"),
    ("22/01/26", "DMRC RECHARGE NEW DELHI METRO", "500", "", "38862.0", "Transport"),
    ("23/01/26", "HPCL PETROL PUMP MUMBAI", "2000", "", "36862.0", "Transport"),
    ("24/01/26", "IOCL AUTO GAS SERVICE PUNE", "450", "", "36412.0", "Transport"),
    ("25/01/26", "IRCTC APP TRAIN TICKET BOOKING", "1150", "", "35262.0", "Transport"),
    ("26/01/26", "UPI-MAKE MY TRIP-mmt@hdfc-708990045607-Flight", "4500", "", "30762.0", "Transport"),

    # Shopping (Unseen apparel brands, electronics stores, truncated)
    ("27/01/26", "UPI-FLPKRT-flpkrt@axis-809001156708-Order", "1499", "", "29263.0", "Shopping"),
    ("28/01/26", "UPI-DECATHLON SPORT-decathlon@icici-910112267809-Gear", "2200", "", "27063.0", "Shopping"),
    ("29/01/26", "UPI-NYKAA BEAUTY-nykaa@hdfc-021223378910-Cosmetics", "980", "", "26083.0", "Shopping"),
    ("30/01/26", "UPI-RELIANCE DIGITAL-rdigital@icici-132334489011-Gadget", "3500", "", "22583.0", "Shopping"),
    ("31/01/26", "POS CROMA ELECTRONICS NOIDA", "2999", "", "19584.0", "Shopping"),
    ("01/02/26", "UPI-ZARA INDIA-zara@kotak-243445590112-Apparel", "4290", "", "15294.0", "Shopping"),
    ("02/02/26", "UPI-H&M ONLINE-hm@icici-354556601213-Clothes", "1999", "", "13295.0", "Shopping"),
    ("03/02/26", "UPI-AMZN-PAY-RETAIL ORDER", "899", "", "12396.0", "Shopping"),

    # Health (Clinics, testing labs, pharmacy)
    ("04/02/26", "UPI-MEDPLUS PHARMACY-medplus@icici-465667712314-Meds", "480", "", "11916.0", "Health"),
    ("05/02/26", "UPI-APOLLO PHARMACY-apollo@hdfc-576778823415-Drugs", "620", "", "11296.0", "Health"),
    ("06/02/26", "POS DR LAL PATHLABS GURGAON", "1500", "", "9796.0", "Health"),
    ("07/02/26", "UPI-MAX HEALTHCARE-max@axis-687889934516-Doctor", "1200", "", "8596.0", "Health"),
    ("08/02/26", "UPI-PRACTO CONSULT-practo@icici-798990045617-Clinic", "700", "", "7896.0", "Health"),

    # Entertainment (Cinema, arcades, PC gaming)
    ("09/02/26", "BMS-TICKETS MOVIE SHOW", "650", "", "7246.0", "Entertainment"),
    ("10/02/26", "UPI-PVR INOX-pvr@hdfc-809001156718-Cinema", "920", "", "6326.0", "Entertainment"),
    ("11/02/26", "UPI-SMAAASH GAMING-smaaash@icici-910112267819-Arcade", "1200", "", "5126.0", "Entertainment"),
    ("12/02/26", "UPI-STEAM GAMES-steam@kotak-021223378920-Gaming", "1499", "", "3627.0", "Entertainment"),

    # Bills & Utilities (State discoms, piped gas, DTH)
    ("13/02/26", "AIRTEL BROADBAND BILL PAYMENT", "1179", "", "2448.0", "Bills & Utilities"),
    ("14/02/26", "BESCOM POWER BENGALURU ELECTRICITY", "1850", "", "598.0", "Bills & Utilities"),
    ("15/02/26", "MAHA DISCOM ELECTRICITY BILL", "2100", "", "28498.0", "Bills & Utilities"),
    ("16/02/26", "IGL PIPED NATURAL GAS RECHARGE", "740", "", "27758.0", "Bills & Utilities"),
    ("17/02/26", "TATA PLAY DTH RECHARGE", "450", "", "27308.0", "Bills & Utilities"),

    # Subscriptions (OTT, Cloud, Apple)
    ("18/02/26", "UPI-HOTSTAR DISNEY-hotstar@icici-132334489021-OTT", "299", "", "27009.0", "Subscriptions"),
    ("19/02/26", "UPI-YOUTUBE PREMIUM-yt@google-243445590122-Sub", "149", "", "26860.0", "Subscriptions"),
    ("20/02/26", "APPLE SERVICES COM BILLING", "219", "", "26641.0", "Subscriptions"),
    ("21/02/26", "UPI-AMAZON PRIME-amznprime@hdfc-354556601223-Sub", "1499", "", "25142.0", "Subscriptions"),

    # Rent & Housing
    ("22/02/26", "NOBROKER RENT PAYMENT FLAT 402", "18000", "", "7142.0", "Rent"),
    ("23/02/26", "UPI-LANDLORD-RENT TRANSFER", "18000", "", "29142.0", "Rent"),

    # Investments (Brokers, US stocks)
    ("24/02/26", "GROWW INVEST TECH SIP MUTUAL FUND", "5000", "", "24142.0", "Investments"),
    ("25/02/26", "ZERODHA BROKING EQUITY ACC", "4000", "", "20142.0", "Investments"),
    ("26/02/26", "INDMONEY US STOCKS DEPOSIT", "3000", "", "17142.0", "Investments"),

    # Transfers (P2P phone numbers, informal descriptors)
    ("27/02/26", "UPI-PAY TO 9876543210-Split", "500", "", "16642.0", "Transfers"),
    ("28/02/26", "UPI-SHARMAJI-PAYMENT", "1200", "", "15442.0", "Transfers"),
    ("01/03/26", "UPI-MOM-GIFT TRANSFER", "3000", "", "12442.0", "Transfers"),
    ("02/03/26", "UPI-ROOMMATE-FLAT EXPENSES", "1850", "", "10592.0", "Transfers"),
    ("03/03/26", "TRANSFER TO ACC 482910 SELF SAVINGS", "5000", "", "5592.0", "Transfers"),

    # Income
    ("01/01/26", "NEFT CR TECH CONSULTANCY SALARY JAN", "", "75000", "80592.0", "Income"),
    ("01/02/26", "IMPS CR FREELANCE DESIGN CLIENT", "", "25000", "105592.0", "Income"),
]


def generate_hard_holdout():
    raw_rows = []
    labels_rows = []

    for d, narr, w, dep, bal, true_cat in HARD_SAMPLES:
        debit = float(w) if w else 0.0
        credit = float(dep) if dep else 0.0
        direction = "credit" if credit > 0 else "debit"
        amount = credit if credit > 0 else debit
        balance = float(bal)
        txn_date = pd.to_datetime(d, format="%d/%m/%y").date()

        class Dummy:
            pass
        r = Dummy()
        r.txn_date = txn_date
        r.narration = narr
        r.amount = amount
        r.direction = direction
        r.balance = balance
        tid = make_txn_id(r)

        raw_rows.append({
            "Date": d,
            "Narration": narr,
            "Chq./Ref.No.": "999888777666",
            "Withdrawal Amt.": w,
            "Deposit Amt.": dep,
            "Closing Balance": bal,
        })
        labels_rows.append({
            "txn_id": tid,
            "true_category": true_cat,
        })

    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    LABELS_CSV.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(raw_rows).to_csv(RAW_CSV, index=False)
    pd.DataFrame(labels_rows).to_csv(LABELS_CSV, index=False)
    print(f"Generated {len(raw_rows)} rows to {RAW_CSV} and {LABELS_CSV}")


if __name__ == "__main__":
    generate_hard_holdout()
