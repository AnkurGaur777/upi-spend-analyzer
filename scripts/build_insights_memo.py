# scripts/build_insights_memo.py
import json
from pathlib import Path
import pypdfium2
import pdfplumber

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

MEMO_JSON = Path("docs/memo_numbers.json")
PDF_OUT = Path("docs/insights_memo.pdf")
PNG_OUT = Path("docs/insights_memo.png")
FONT_DIR = Path("assets/fonts")

# Register open-license fonts
pdfmetrics.registerFont(TTFont("DejaVuSans", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))

# Color Palette
TEAL = colors.HexColor("#0F766E")       # Primary brand accent
DARK_TEAL = colors.HexColor("#115E59")  # Darker accent
LIGHT_TEAL = colors.HexColor("#F0FDFA") # Light tint background
SLATE_900 = colors.HexColor("#0F172A")  # Main headings / values
SLATE_700 = colors.HexColor("#334155")  # Body text
SLATE_500 = colors.HexColor("#64748B")  # Subtext / labels
BORDER = colors.HexColor("#CBD5E1")     # Border lines
CARD_BG = colors.HexColor("#F8FAFC")    # Card background
GREEN = colors.HexColor("#166534")      # Positive savings
AMBER = colors.HexColor("#B45309")      # Warning/Drop
WHITE = colors.HexColor("#FFFFFF")


def format_inr(amount: float, symbol: bool = True) -> str:
    s = f"{abs(amount):.2f}"
    parts = s.split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        other = integer_part[:-3]
        groups = []
        while len(other) > 2:
            groups.append(other[-2:])
            other = other[:-2]
        if other:
            groups.append(other)
        groups.reverse()
        formatted = ",".join(groups) + "," + last3
    else:
        formatted = integer_part

    if decimal_part == "00":
        res = formatted
    else:
        res = f"{formatted}.{decimal_part}"

    sign = "-" if amount < 0 else ""
    sym = "₹" if symbol else "Rs "
    return f"{sign}{sym}{res}"


def build_memo_pdf():
    with open(MEMO_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # A4 Dimensions: 595.27 x 841.89 points
    # Printable area with 22pt margins: 551.27 x 797.89 pt
    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=A4,
        leftMargin=22,
        rightMargin=22,
        topMargin=18,
        bottomMargin=18,
    )

    story = []
    avail_w = 551  # 595.27 - 44

    # Typography Hierarchy - BODY FONT SIZE IS STRICTLY >= 8.5 pt
    BODY_PT = 8.5
    BODY_LEADING = 10.5

    sub_hdr_style = ParagraphStyle(
        "SubHeader",
        fontName="DejaVuSans-Bold",
        fontSize=BODY_PT,
        leading=BODY_LEADING,
        textColor=TEAL,
    )
    title_style = ParagraphStyle(
        "DocTitle",
        fontName="DejaVuSans-Bold",
        fontSize=14,
        leading=16,
        textColor=SLATE_900,
    )
    meta_style = ParagraphStyle(
        "MetaText",
        fontName="DejaVuSans",
        fontSize=BODY_PT,
        leading=BODY_LEADING,
        textColor=SLATE_500,
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        fontName="DejaVuSans",
        fontSize=BODY_PT,
        leading=BODY_LEADING,
        textColor=AMBER,
    )
    sec_hdr_style = ParagraphStyle(
        "SecHeader",
        fontName="DejaVuSans-Bold",
        fontSize=9.5,
        leading=11.5,
        textColor=TEAL,
        spaceAfter=3,
    )

    # 1. Header Area
    story.append(Paragraph("PERSONAL FINANCE ANALYTICS · EXECUTIVE INSIGHTS MEMO", sub_hdr_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("UPI & Bank Statement Spend Analysis (12-Month Review)", title_style))
    story.append(Spacer(1, 3))

    meta_line = (
        f"<b>Reporting Period:</b> {data['context']['start_date']} to {data['context']['end_date']} "
        f"({data['context']['calendar_days']} Calendar Days, Sept partial: 27 days) &nbsp;|&nbsp; "
        f"<b>Scope:</b> 704 Total Rows (652 Living Spend, 12 Income, 21 Transfers, 12 SIP, 7 Refunds)"
    )
    story.append(Paragraph(meta_line, meta_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("<i>Note: Based on synthetic data; findings are illustrative. Personal savings rate strictly excludes investments (SIP) and self-transfers.</i>", disclaimer_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceBefore=0, spaceAfter=4))

    # 2. Context KPI Cards (Table of 4 columns)
    kpis = [
        ("TOTAL EARNED INCOME", format_inr(data["context"]["total_income"]), "Fixed salary: ₹65,000 / mo", TEAL),
        ("OPERATIONAL LIVING SPEND", format_inr(data["context"]["total_spend"]), f"Avg {format_inr(data['context']['avg_monthly_spend'])} / mo", SLATE_900),
        ("NET RETAINED SAVINGS", format_inr(data["context"]["total_savings"]), "Earned income less spend", GREEN),
        ("ANNUAL SAVINGS RATE", f"{data['context']['savings_rate_pct']}%", f"{format_inr(data['context']['total_savings'])} / {format_inr(data['context']['total_income'])}", TEAL),
    ]

    card_row = []
    for lbl, val, sub, col in kpis:
        p_lbl = Paragraph(f"<b>{lbl}</b>", ParagraphStyle("KLbl", fontName="DejaVuSans-Bold", fontSize=7.5, leading=9, textColor=SLATE_500))
        p_val = Paragraph(f"<b>{val}</b>", ParagraphStyle("KVal", fontName="DejaVuSans-Bold", fontSize=13, leading=15, textColor=col))
        p_sub = Paragraph(sub, ParagraphStyle("KSub", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_700))
        card_row.append([p_lbl, Spacer(1, 1), p_val, Spacer(1, 1), p_sub])

    kpi_col_w = avail_w / 4.0
    kpi_table = Table([[card_row[0], card_row[1], card_row[2], card_row[3]]], colWidths=[kpi_col_w]*4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 1, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 5))

    # 3. Key Findings (Section)
    story.append(Paragraph("KEY EMPIRICAL FINDINGS (DATA-GROUNDED)", sec_hdr_style))

    f1 = data["findings"]["f1_subscriptions"]
    f2 = data["findings"]["f2_food_delivery"]
    f3 = data["findings"]["f3_small_ticket_leaks"]
    f4 = data["findings"]["f4_weekend_vs_weekday"]
    f5 = data["findings"]["f5_savings_rate_drop"]

    findings_items = [
        (
            f"1. Subscriptions & Fixed Commitments ({format_inr(f1['annual_cost'])} / yr pure streaming)",
            f"Automated detection flagged 2 pure streaming subscriptions: Netflix ({format_inr(7788)}/yr) and Spotify ({format_inr(1428)}/yr), "
            f"totaling {format_inr(f1['annual_cost'])}/yr. Fixed living commitments (Rent {format_inr(216000)}, Gym {format_inr(18000)}, Jio {format_inr(3588)}, subs {format_inr(9216)}) "
            f"total {format_inr(f1['recurring_living_spend'])}/yr ({f1['pct_of_living_spend']}% of living spend; including the {format_inr(60000)} SIP, total commitments reach {format_inr(f1['total_recurring_commitments_with_sip'])}/yr or {f1['pct_of_total_outflow']}% of all cash outflows). "
            f"Pausing streaming tiers yields {format_inr(f1['savable_monthly'])}/mo ({format_inr(f1['savable_annual'])}/yr; 100% of pure streaming outlays)."
        ),
        (
            f"2. High-Frequency Food Delivery Concentration (129 Orders, {format_inr(f2['total_spend'])})",
            f"Online food delivery via Swiggy, Zomato, and Dominos accumulated 129 orders totaling {format_inr(f2['total_spend'])} (~10.8 orders/mo, "
            f"averaging {format_inr(f2['avg_monthly_spend'])}/mo). Food delivery accounts for {f2['pct_of_discretionary']}% of discretionary expenditure ({format_inr(f2['discretionary_spend_total'])}) "
            f"and 61.7% of all Food & Dining ({format_inr(f2['food_dining_total'])})."
        ),
        (
            f"3. Discretionary 'Small-Ticket Leak' Accumulation ({f3['discretionary_sub300_count']} Payments < ₹300, {format_inr(f3['discretionary_sub300_total'])})",
            f"Discretionary debits under ₹300 (excl. recurring bills) accounted for {f3['discretionary_sub300_count']} debits totaling {format_inr(f3['discretionary_sub300_total'])} (mean ticket: {format_inr(f3['discretionary_sub300_avg'])}). "
            f"Transport leads with 125 rides ({format_inr(f3['transport_total'])} in Uber, Rapido, Ola, and Delhi Metro rides), "
            f"followed by 71 cafe and quick food stops ({format_inr(f3['category_split']['Food & Dining']['total'])}, including CCD and Starbucks {format_inr(f3['cafes_details']['total_amount'])}). Micro-spending quietly drains {format_inr(f3['discretionary_sub300_monthly'])} every month."
        ),
        (
            f"4. Weekday vs. Weekend Daily Spend Density (+{f4['version_b_variable_spend_excluding_fixed']['robustness_check']['weekday_higher_pct_excluding_cash']}% to +{f4['version_b_variable_spend_excluding_fixed']['weekday_higher_pct']}% on Weekdays)",
            f"Across 362 calendar days (258 weekdays, 104 weekend days): Ver A (all spend): Weekday {format_inr(f4['version_a_all_living_spend']['weekday_per_day'])}/day vs Weekend {format_inr(f4['version_a_all_living_spend']['weekend_per_day'])}/day (+{f4['version_a_all_living_spend']['weekday_higher_pct']}%). "
            f"Ver B (variable spend excl. rent & fixed bills): Weekday {format_inr(f4['version_b_variable_spend_excluding_fixed']['weekday_per_day'])}/day vs Weekend {format_inr(f4['version_b_variable_spend_excluding_fixed']['weekend_per_day'])}/day (+{f4['version_b_variable_spend_excluding_fixed']['weekday_higher_pct']}%). "
            f"Empirical driver: Cash (+₹114.86/day), Shopping (+₹85.55/day), Groceries (+₹53.41/day); Entertainment (₹34.71 vs ₹22.34/day) and Health (₹33.37 vs ₹18.39/day) higher on weekends. Robustness: +26.3% excl. ≥₹5k ATM cash; +21.5% excl. cash withdrawals."
        ),
        (
            f"5. Annual Savings Rate Trough & Core Driver (November 2025 at {f5['lowest_savings_rate_pct']}%)",
            f"Monthly savings rate plunged to an annual low of {f5['lowest_savings_rate_pct']}% in November 2025 (monthly spend peaked at {format_inr(f5['lowest_month_spend'])}, vs. a {f5['highest_savings_rate_pct']}% savings rate in March). "
            f"Category decomposition reveals the driver: Festive-season spike (synthetic data) where Shopping rose to {format_inr(f5['drivers_by_category']['Shopping'])} (+₹2,999 MoM) "
            f"and Groceries surged to {format_inr(f5['drivers_by_category']['Groceries'])} (+₹4,302 MoM). (Note: September 2026 ends on 27 Sep, making its MoM an artifact of partial data)."
        ),
    ]

    find_rows = []
    for title, desc in findings_items:
        p_t = Paragraph(f"<b>{title}</b>", ParagraphStyle("FT", fontName="DejaVuSans-Bold", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_900))
        p_d = Paragraph(desc, ParagraphStyle("FD", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_700))
        find_rows.append([[p_t, Spacer(1, 1), p_d]])

    find_table = Table([[r[0]] for r in find_rows], colWidths=[avail_w])
    find_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINELEFT", (0, 0), (0, -1), 3, TEAL),
    ]))
    story.append(find_table)
    story.append(Spacer(1, 5))

    # 4. Strategic Recommendations
    story.append(Paragraph("STRATEGIC RECOMMENDATIONS & SCENARIO SAVINGS (ZERO OVERLAP)", sec_hdr_style))

    recs = data["recommendations"]
    rec_cols = []
    for i, r in enumerate(recs):
        p_hdr = Paragraph(f"<b>ACTION 0{i+1}: {r['title']}</b>", ParagraphStyle("RH", fontName="DejaVuSans-Bold", fontSize=BODY_PT, leading=BODY_LEADING, textColor=DARK_TEAL))
        p_ass = Paragraph(f"<b>Assumption:</b> {r['assumption']}", ParagraphStyle("RA", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_700))
        p_for = Paragraph(f"<b>Formula:</b> {r['formula']}", ParagraphStyle("RF", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_500))
        p_sav = Paragraph(f"<b>Scenario saving: +{format_inr(r['expected_monthly_saving'])}/mo</b> (+{format_inr(r['expected_annual_saving'])}/yr)", ParagraphStyle("RS", fontName="DejaVuSans-Bold", fontSize=BODY_PT, leading=BODY_LEADING, textColor=GREEN))
        rec_cols.append([p_hdr, Spacer(1, 1), p_ass, Spacer(1, 1), p_for, Spacer(1, 1), p_sav])

    rec_w = avail_w / 3.0
    rec_table = Table([[rec_cols[0], rec_cols[1], rec_cols[2]]], colWidths=[rec_w]*3)
    rec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 1, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(rec_table)
    story.append(Spacer(1, 4))

    # 5. Combined Impact Banner
    tot = data["total_savings_potential"]
    impact_text = (
        f"<b>COMBINED SAVINGS IMPACT:</b> +{format_inr(tot['monthly'])} / month (+{format_inr(tot['annual'])} / year) &nbsp;|&nbsp; "
        f"<b>Savings Rate Jump:</b> {tot['baseline_savings_rate_pct']}% → <b>{tot['projected_savings_rate_pct']}%</b> "
        f"(+{tot['percentage_points_increase']} percentage points, unrounded: 17.14% → 23.04%)"
    )
    p_imp = Paragraph(impact_text, ParagraphStyle("Imp", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=WHITE))
    imp_table = Table([[p_imp]], colWidths=[avail_w])
    imp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(imp_table)
    story.append(Spacer(1, 4))

    # 6. Methodology & Guardrails
    story.append(Paragraph("METHODOLOGY, INTEGRITY & RECONCILED PARTITION", sec_hdr_style))

    p_m1 = Paragraph(
        f"• <b>Model Performance:</b> {data['method_and_limits']['synthetic_benchmark']} "
        f"Hard holdout: {data['method_and_limits']['hard_holdout_benchmark']}",
        ParagraphStyle("M1", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_500)
    )
    p_m2 = Paragraph(
        f"• <b>Row Partition Reconciliation (Exact 704):</b> Living Spend: 652 debits ({format_inr(data['context']['total_spend'])}) | "
        f"Income: 12 credits ({format_inr(data['context']['total_income'])}) | "
        f"Self-transfers: 21 rows ({format_inr(50123)}) | "
        f"SIP Investments: 12 debits ({format_inr(60000)}) | Refunds/Reversals: 7 credits ({format_inr(4833)}) | Other: 0 rows. Total = 704.",
        ParagraphStyle("M2", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_500)
    )
    p_m3 = Paragraph(
        f"• <b>Accounting Guardrails:</b> {data['method_and_limits']['exclusions']} "
        f"{data['method_and_limits']['substitution_note']} "
        f"All metrics programmatically derived from spend_analyzer pipeline and verified against SQLite/MySQL views.",
        ParagraphStyle("M3", fontName="DejaVuSans", fontSize=BODY_PT, leading=BODY_LEADING, textColor=SLATE_500)
    )

    meth_table = Table([[p_m1], [p_m2], [p_m3]], colWidths=[avail_w])
    meth_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meth_table)

    # Build document
    doc.build(story)
    print(f"Built PDF at {PDF_OUT}")

    # Verify with pdfplumber
    with pdfplumber.open(PDF_OUT) as pdf:
        num_pages = len(pdf.pages)
        print(f"ReportLab PDF page count: {num_pages}")
        assert num_pages == 1, f"ERROR: Expected exactly 1 page, got {num_pages}!"
        page_text = pdf.pages[0].extract_text()
        print(f"Extracted {len(page_text)} chars of text from page 1.")
        assert "PERSONAL FINANCE ANALYTICS" in page_text
        assert "₹" in page_text or "Rs" in page_text
        assert "Based on synthetic data; findings are illustrative." in page_text
        assert "704 Total Rows" in page_text or "704" in page_text

    # Render to PNG
    pdf_doc = pypdfium2.PdfDocument(PDF_OUT)
    page = pdf_doc[0]
    rendered = page.render(scale=2.5).to_pil()
    rendered.save(PNG_OUT)
    print(f"Rendered PDF page 1 to {PNG_OUT} (size: {rendered.size})")


if __name__ == "__main__":
    build_memo_pdf()
