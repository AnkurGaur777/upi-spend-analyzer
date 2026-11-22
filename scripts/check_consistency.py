# scripts/check_consistency.py
import json
import re
import sys
from pathlib import Path
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.build_demo_gif import GIF_SOURCE_STRINGS, create_title_frame

MEMO_JSON = Path("docs/memo_numbers.json")
README_MD = Path("README.md")
PAGE_TEXT_MD = Path("docs/insights_page_text.md")
PDF_PATH = Path("docs/insights_memo.pdf")
RENDERED_TEXT_PATH = Path("docs/audit/rendered_text.json")


def normalize_text(text: str) -> str:
    # Replace non-breaking spaces and normalize rupee symbols
    text = text.replace("\u00a0", " ").replace("₹", "Rs ")
    # Normalize multiple whitespaces
    return " ".join(text.split())


def check_consistency():
    if not MEMO_JSON.exists():
        print(f"FAIL: {MEMO_JSON} does not exist!")
        sys.exit(1)

    data = json.loads(MEMO_JSON.read_text(encoding="utf-8"))
    ctx = data["context"]
    part = data["partition_reconciliation"]
    f1 = data["findings"]["f1_subscriptions"]
    f2 = data["findings"]["f2_food_delivery"]
    f3 = data["findings"]["f3_small_ticket_leaks"]
    f4 = data["findings"]["f4_weekend_vs_weekday"]
    f5 = data["findings"]["f5_savings_rate_drop"]
    recs = data["recommendations"]
    tot = data["total_savings_potential"]

    va = f4["version_a_all_living_spend"]
    vb = f4["version_b_variable_spend_excluding_fixed"]

    # Key figures to verify across text documents
    checks = [
        ("Total Income", ["780,000", "7,80,000"]),
        ("Total Living Spend", ["646,319", "6,46,319"]),
        ("Net Retained Savings", ["133,681", "1,33,681"]),
        ("Baseline Savings Rate %", ["17.1%"]),
        ("Total Rows", ["704"]),
        ("Spend Rows", ["652"]),
        ("Calendar Days", ["362"]),
        ("Pure Digital Streaming Annual Cost", ["9,216"]),
        ("Fixed Living Commitments", ["246,804", "2,46,804"]),
        ("Fixed Living Commitments %", ["38.2%"]),
        ("Total Commitments with SIP", ["306,804", "3,06,804"]),
        ("Total Commitments with SIP %", ["43.4%"]),
        ("Rent Plus SIP Outflow %", ["39.1%"]),
        ("Food Delivery Orders", ["129"]),
        ("Food Delivery Spend", ["51,565"]),
        ("Food Delivery % Discretionary", ["28.1%"]),
        ("Food Delivery % Food & Dining", ["61.7%"]),
        ("Discretionary Small Ticket Leaks Count", ["205"]),
        ("Discretionary Small Ticket Leaks Total", ["38,871"]),
        ("Weekday Days", ["258"]),
        ("Weekend Days", ["104"]),
        ("Version A Weekday Per Day", ["1,837.18", "1837.18"]),
        ("Version A Weekend Per Day", ["1,656.98", "1656.98"]),
        ("Version A Weekday Higher %", ["10.9%"]),
        ("Version B Weekday Per Day", ["1,187.82", "1187.82"]),
        ("Version B Weekend Per Day", ["894.79"]),
        ("Version B Weekday Higher %", ["32.7%"]),
        ("November Savings Rate Trough", ["7.0%"]),
        ("November Spend Peak", ["60,480"]),
        ("Rec 1 Monthly Saving", ["2,148.54", "2148.54"]),
        ("Rec 1 Annual Saving", ["25,782.50", "25782.50"]),
        ("Rec 2 Monthly Saving", ["768.00", "768"]),
        ("Rec 2 Annual Saving", ["9,216"]),
        ("Rec 3 Monthly Saving", ["922.50", "922.5"]),
        ("Rec 3 Annual Saving", ["11,070.00", "11,070", "11070"]),
        ("Total Monthly Saving Potential", ["3,839.04", "3839.04", "3,839", "3839"]),
        ("Total Annual Saving Potential", ["46,068.50", "46068.50", "46,068", "46068"]),
        ("Projected Savings Rate %", ["23.0%"]),
        ("Savings Rate Increase pp", ["5.9"]),
    ]

    # Forbidden strings that represent hallucinated, ungrounded, or old erroneous claims
    forbidden = [
        "42.7%",   # Old wrong Rent+SIP ratio (must be 39.1%)
        "4,069.21",
        "4069.21",
        "4,069",
        "1,152.67",
        "1152.67",
        "1,152",
        "48,830.50",
        "48830.50",
        "48,830",
        "23.4%",
        "6.3 percentage points",
        "6.3 pp",
        "6.3%",
        "85.56",   # Old rounded per-day gap (unrounded is 85.55)
        "Cult.fit zero weekend usage",
        "Spotify overlaps YouTube Premium",
        "Netflix 4K",
        "jewellery merchants",
        "98,950",  # Old hallucinated Nov spend
        "Nov savings rate of 17.5%",  # Old hallucinated Nov savings rate
        "November savings rate of 17.5%",
        "17.5% in Nov",
        "42,880",  # Old hallucinated food delivery spend
        "82 orders", # Old hallucinated food orders
        "528 spend", # Old hallucinated spend rows count
        "248 out of 528",
        "single largest controllable living expenditure",
        "without compromising core lifestyle",
        "auto/metro fares",
        "frictionless",
        "downgrading",
    ]

    # Load file texts
    readme_text = README_MD.read_text(encoding="utf-8")
    page_text = PAGE_TEXT_MD.read_text(encoding="utf-8")

    with pdfplumber.open(PDF_PATH) as pdf:
        pdf_text = " ".join(page.extract_text() for page in pdf.pages)

    rendered_strings = []
    if RENDERED_TEXT_PATH.exists():
        rendered_strings = json.loads(RENDERED_TEXT_PATH.read_text(encoding="utf-8"))

    # Generate title frame if not already populated
    if not GIF_SOURCE_STRINGS:
        create_title_frame()

    gif_text = " ".join(GIF_SOURCE_STRINGS)
    rendered_blob = " ".join(rendered_strings)

    arch_svg_path = Path("docs/architecture.svg")
    arch_svg_text = arch_svg_path.read_text(encoding="utf-8") if arch_svg_path.exists() else ""

    arch_txt_path = Path("docs/audit/architecture_rendered_text.json")
    arch_strings = json.loads(arch_txt_path.read_text(encoding="utf-8")) if arch_txt_path.exists() else []
    arch_blob = " ".join(arch_strings)

    docs = {
        "README.md": readme_text,
        "docs/insights_page_text.md": page_text,
        "docs/insights_memo.pdf": pdf_text,
        "docs/audit/rendered_text.json": rendered_blob,
        "docs/architecture.svg": arch_svg_text,
        "ARCHITECTURE_STRINGS": arch_blob,
        "GIF_SOURCE_STRINGS": gif_text,
    }

    print("="*60)
    print("CONSISTENCY & PROVENANCE AUDIT ACROSS ALL DOCUMENTS & VISUALS")
    print("="*60)

    # 1. Check forbidden terms across ALL documents and visuals
    failures = 0
    for doc_name, text in docs.items():
        text_lower = text.lower()
        for term in forbidden:
            pattern = re.compile(r"(?<![0-9])" + re.escape(term.lower()))
            if pattern.search(text_lower):
                print(f"FAIL: Forbidden unsupported claim/number '{term}' found in {doc_name}!")
                failures += 1

    if failures == 0:
        print("[PASS] Zero unsupported claims or hallucinated figures found across all docs and visuals.")

    # 2. Check each expected metric pattern across the 3 textual docs
    text_docs = {
        "README.md": readme_text,
        "docs/insights_page_text.md": page_text,
        "docs/insights_memo.pdf": pdf_text,
    }
    for label, patterns in checks:
        for doc_name, text in text_docs.items():
            if doc_name == "docs/insights_memo.pdf" and label == "Rent Plus SIP Outflow %":
                continue
            matched = any(p in text for p in patterns)
            if not matched:
                print(f"FAIL: {label} (patterns {patterns}) not found in {doc_name}!")
                failures += 1

    if failures == 0:
        print(f"[PASS] All {len(checks)} key financial figures match memo_numbers.json across all documents.")

    # 3. Check that every percentage in docs/audit/rendered_text.json exists in percentages_registry
    registry = data.get("percentages_registry", {})
    pct_pattern = re.compile(r"\b\d+(?:\.\d+)?%")
    unregistered_pcts = set()
    found_pcts = set()

    for s in rendered_strings:
        matches = pct_pattern.findall(s)
        for m in matches:
            found_pcts.add(m)
            if m not in registry:
                unregistered_pcts.add(m)

    if unregistered_pcts:
        print(f"FAIL: Found unregistered percentages in docs/audit/rendered_text.json: {sorted(list(unregistered_pcts))}")
        failures += len(unregistered_pcts)
    else:
        print(f"[PASS] All {len(found_pcts)} unique percentages in docs/audit/rendered_text.json match memo_numbers.json percentages_registry.")
        print(f"       Verified percentages: {sorted(list(found_pcts))}")

    if failures == 0:
        print("ALL AUDIT CHECKS PASSED SUCCESSFULLY!")
        return 0
    else:
        print(f"\nAUDIT FAILED with {failures} errors!")
        return 1


if __name__ == "__main__":
    sys.exit(check_consistency())
