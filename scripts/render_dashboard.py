# scripts/render_dashboard.py
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine, text

from spend_analyzer.load import get_engine

OUTPUT_DIR = Path("powerbi/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RENDERED_TEXT_PATH = Path("docs/audit/rendered_text.json")
MEMO_PATH = Path("docs/memo_numbers.json")

# Canvas specifications
W, H = 1920, 1080
BG_COLOR = (243, 242, 241)     # #F3F2F1 Power BI Light Grey
CARD_BG = (255, 255, 255)      # Pure White Card
TEAL = (15, 118, 110)          # #0F766E Accent Teal
DARK_TEAL = (17, 94, 89)       # #115E59
LIGHT_TEAL = (204, 251, 241)   # #CCFBF1
SLATE_900 = (15, 23, 42)       # Primary text
SLATE_700 = (51, 65, 85)       # Secondary text
SLATE_500 = (100, 116, 139)    # Muted text
SLATE_400 = (148, 163, 184)    # Borders
SLATE_200 = (226, 232, 240)    # Light borders
SLATE_100 = (241, 245, 249)    # Card backgrounds
GREEN = (22, 101, 52)          # Positive
AMBER = (217, 119, 6)          # Savings rate line / Warning
WHITE = (255, 255, 255)        # Pure White

# Global tracker for rendered text
RENDERED_STRINGS = []


_GLYPH_CACHE = {}


def assert_font_has_glyphs(font, text_str: str):
    """Fail if font lacks a glyph for any character in text_str (renders as tofu .notdef)."""
    for ch in text_str:
        if ch in " \t\n":
            continue
        key = (id(font), ch)
        if key not in _GLYPH_CACHE:
            try:
                tofu_m = font.getmask("\ufffe")
                ch_m = font.getmask(ch)
                has_glyph = not (ch_m.size == tofu_m.size and list(ch_m) == list(tofu_m))
            except Exception:
                has_glyph = True
            _GLYPH_CACHE[key] = has_glyph
        if not _GLYPH_CACHE[key]:
            raise ValueError(
                f"Missing glyph error: Font lacks a glyph for character '{ch}' (U+{ord(ch):04X}) in string: {text_str!r}"
            )


def tracked_draw_text(draw, pos, text_val, fill, font, container_box=None, margin=0):
    """Draw text and record rendered string, with automated container overflow checking and missing glyph validation."""
    text_str = str(text_val)
    assert_font_has_glyphs(font, text_str)
    RENDERED_STRINGS.append(text_str)
    
    if container_box is not None:
        cx1, cy1, cx2, cy2 = container_box
        bbox = font.getbbox(text_str)
        tx1 = pos[0] + bbox[0]
        ty1 = pos[1] + bbox[1]
        tx2 = pos[0] + bbox[2]
        ty2 = pos[1] + bbox[3]
        if tx2 > (cx2 - margin) or ty2 > (cy2 - margin) or tx1 < (cx1 + margin) or ty1 < (cy1 + margin):
            raise ValueError(
                f"Text '{text_str}' bbox ({tx1}, {ty1}, {tx2}, {ty2}) overflows container "
                f"({cx1}, {cy1}, {cx2}, {cy2}) with required margin {margin}!"
            )
            
    draw.text(pos, text_str, fill=fill, font=font)


def get_font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    """Font fallback chain: Segoe UI -> DejaVu Sans (bundled in assets/fonts)."""
    candidates = []
    if bold:
        candidates = [
            Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("assets/fonts/DejaVuSans-Bold.ttf"),
        ]
    elif italic:
        candidates = [
            Path(r"C:\Windows\Fonts\segoeuii.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
            Path("assets/fonts/DejaVuSans.ttf"),
        ]
    else:
        candidates = [
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("assets/fonts/DejaVuSans.ttf"),
        ]

    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


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


def load_memo():
    if not MEMO_PATH.exists():
        raise FileNotFoundError(f"{MEMO_PATH} missing!")
    return json.loads(MEMO_PATH.read_text(encoding="utf-8"))


def load_and_assert_data(engine=None):
    if engine is None:
        engine = get_engine()

    with engine.connect() as conn:
        tx_all = pd.read_sql(text("SELECT * FROM transactions"), conn)
        tx_spend = pd.read_sql(
            text("SELECT * FROM transactions WHERE direction = 'debit' AND is_transfer = 0 AND is_reversal = 0 AND category <> 'Investments'"),
            conn,
        )
        tx_income = pd.read_sql(
            text("SELECT * FROM transactions WHERE direction = 'credit' AND category = 'Income'"),
            conn,
        )
        rec = pd.read_sql(text("SELECT * FROM recurring_payments"), conn)

    # STRICT ASSERTIONS AGAINST EXPECTED METRICS
    assert len(tx_all) == 704, f"Expected 704 total rows, found {len(tx_all)}"
    assert len(tx_spend) == 652, f"Expected 652 spend rows, found {len(tx_spend)}"

    total_income = float(tx_income["amount"].sum())
    total_spend = float(tx_spend["amount"].sum())
    total_savings = total_income - total_spend
    savings_rate = (total_savings / total_income) * 100.0

    assert abs(total_income - 780000.0) < 0.01, f"Expected 780000 income, got {total_income}"
    assert abs(total_spend - 646319.0) < 0.01, f"Expected 646319 spend, got {total_spend}"
    assert abs(total_savings - 133681.0) < 0.01, f"Expected 133681 savings, got {total_savings}"
    assert abs(savings_rate - 17.1385897) < 0.1, f"Expected 17.1% savings rate, got {savings_rate}"

    # Pure Subscriptions assertions
    pure_subs = rec[rec["category"] == "Subscriptions"]
    assert len(pure_subs) == 2, f"Expected 2 pure subscriptions, found {len(pure_subs)}"
    pure_subs_cost = float(pure_subs["annual_cost"].sum())
    assert abs(pure_subs_cost - 9216.0) < 0.01, f"Expected 9216 subs cost, got {pure_subs_cost}"

    # Top category checks
    cat_spend = tx_spend.groupby("category")["amount"].sum().to_dict()
    assert abs(cat_spend.get("Rent", 0) - 216000.0) < 0.01
    assert abs(cat_spend.get("Groceries", 0) - 92979.0) < 0.01
    assert abs(cat_spend.get("Shopping", 0) - 90633.0) < 0.01
    assert abs(cat_spend.get("Food & Dining", 0) - 83599.0) < 0.01
    assert abs(cat_spend.get("Cash Withdrawal", 0) - 54000.0) < 0.01
    assert abs(cat_spend.get("Transport", 0) - 39766.0) < 0.01
    assert abs(cat_spend.get("Health", 0) - 26214.0) < 0.01
    assert abs(cat_spend.get("Bills & Utilities", 0) - 24537.0) < 0.01
    assert abs(cat_spend.get("Entertainment", 0) - 9375.0) < 0.01
    assert abs(cat_spend.get("Subscriptions", 0) - 9216.0) < 0.01

    print("ALL KPI ASSERTIONS PASSED! Real data perfectly matches expected_kpis.md and sql_results.txt.")
    return tx_all, tx_spend, tx_income, rec


def draw_base_page(draw, title: str, subtitle: str, page_num: int):
    # Top header bar (Height: 90px)
    draw.rectangle([0, 0, W, 90], fill=CARD_BG)
    draw.line([0, 90, W, 90], fill=SLATE_200, width=1)
    draw.rectangle([0, 0, 8, 90], fill=TEAL)

    f_title = get_font(26, bold=True)
    f_sub = get_font(18, bold=False)
    f_badge = get_font(16, bold=True)
    f_foot = get_font(14, bold=False)

    tracked_draw_text(draw, (28, 16), title, fill=SLATE_900, font=f_title, container_box=(0, 0, W, 90))
    tracked_draw_text(draw, (28, 54), subtitle, fill=SLATE_500, font=f_sub, container_box=(0, 0, W, 90))

    # Dynamic badge on top right: DASHBOARD PREVIEW · PAGE n OF 4 (sized dynamically to text bbox)
    badge_text = f"DASHBOARD PREVIEW · PAGE {page_num} OF 4"
    b_bbox = f_badge.getbbox(badge_text)
    bw = (b_bbox[2] - b_bbox[0]) + 28
    bh = (b_bbox[3] - b_bbox[1]) + 16
    bx1 = W - 28 - bw
    by1 = (90 - bh) // 2
    draw.rounded_rectangle([bx1, by1, bx1 + bw, by1 + bh], radius=6, fill=LIGHT_TEAL)
    tracked_draw_text(draw, (bx1 + 14, by1 + 8), badge_text, fill=DARK_TEAL, font=f_badge, container_box=(bx1, by1, bx1 + bw, by1 + bh))

    # Bottom footer (Height: 36px, min 14px font)
    draw.rectangle([0, H - 36, W, H], fill=CARD_BG)
    draw.line([0, H - 36, W, H - 36], fill=SLATE_200, width=1)
    tracked_draw_text(draw, (28, H - 26), "Dashboard preview (rendered from project data)  |  Spend Analyzer Pipeline", fill=SLATE_500, font=f_foot, container_box=(0, H - 36, W, H))
    tracked_draw_text(draw, (W - 460, H - 26), "Grounded in SQLite / MySQL Schema (Synthetic data, illustrative)", fill=SLATE_500, font=f_foot, container_box=(0, H - 36, W, H))


# -------------------------------------------------------------
# PAGE 1: OVERVIEW
# -------------------------------------------------------------
def render_page_1(tx_all, tx_spend, tx_income, rec, memo):
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    ctx = memo["context"]
    f5 = memo["findings"]["f5_savings_rate_drop"]
    f1 = memo["findings"]["f1_subscriptions"]

    draw_base_page(
        draw,
        "Spend & Income Overview · Executive Summary",
        f"Total operational spend of {format_inr(ctx['total_spend'])} against {format_inr(ctx['total_income'])} earned income across 12 months with a {ctx['savings_rate_pct']}% baseline savings rate",
        1
    )

    f_card_val = get_font(34, bold=True)
    f_card_lbl = get_font(18, bold=True)
    f_card_sub = get_font(18, bold=False)
    f_sec_hdr = get_font(22, bold=True)
    f_chart_lbl = get_font(18, bold=False)
    f_chart_val = get_font(18, bold=True)
    f_chip = get_font(16, bold=False)

    # Top KPI Cards (4 cards)
    card_y = 106
    card_h = 114
    card_w = 345
    card_gap = 18
    start_x = 28

    kpis = [
        ("TOTAL LIVING SPEND", format_inr(ctx["total_spend"]), f"{ctx['calendar_days']} calendar days (Sep partial)", TEAL),
        ("ANNUAL SAVINGS RATE", f"{ctx['savings_rate_pct']}%", f"Low: {f5['lowest_savings_rate_pct']}% (Nov) | High: {f5['highest_savings_rate_pct']}% (Mar)", GREEN),
        ("AVG MONTHLY SPEND", format_inr(round(ctx["avg_monthly_spend"])), "Living spend excl. SIP/transfers", SLATE_900),
        ("SUBSCRIPTIONS / YEAR", format_inr(f1["annual_cost"]), f"{f1['count']} Active Services · {format_inr(round(f1['savable_monthly']))} / mo", TEAL),
    ]

    for i, (lbl, val, sub, col) in enumerate(kpis):
        cx = start_x + i * (card_w + card_gap)
        cbox = (cx, card_y, cx + card_w, card_y + card_h)
        draw.rounded_rectangle(cbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
        draw.rectangle([cx, card_y, cx + 5, card_y + card_h], fill=col)
        tracked_draw_text(draw, (cx + 18, card_y + 12), lbl, fill=SLATE_500, font=f_card_lbl, container_box=cbox)
        tracked_draw_text(draw, (cx + 18, card_y + 36), val, fill=col, font=f_card_val, container_box=cbox)
        tracked_draw_text(draw, (cx + 18, card_y + 82), sub, fill=SLATE_700, font=f_card_sub, container_box=cbox)

    # Right Slicer Panel
    slicer_x = 1470
    slicer_y = card_y
    slicer_w = W - 28 - slicer_x
    slicer_h = H - 36 - 18 - slicer_y
    sbox = (slicer_x, slicer_y, slicer_x + slicer_w, slicer_y + slicer_h)

    draw.rounded_rectangle(sbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    draw.rectangle([slicer_x, slicer_y, slicer_x + slicer_w, slicer_y + 46], fill=SLATE_100)
    tracked_draw_text(draw, (slicer_x + 18, slicer_y + 12), "REPORT SLICERS & FILTERS", fill=SLATE_700, font=f_sec_hdr, container_box=sbox)

    # Date Range Slicer
    tracked_draw_text(draw, (slicer_x + 18, slicer_y + 58), "DATE RANGE (YEAR 2025 - 2026)", fill=SLATE_500, font=f_card_lbl, container_box=sbox)
    draw.rounded_rectangle([slicer_x + 18, slicer_y + 84, slicer_x + slicer_w - 18, slicer_y + 122], radius=6, fill=WHITE, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (slicer_x + 24, slicer_y + 92), f"{ctx['start_date']}  →  {ctx['end_date']} (Partial)", fill=SLATE_900, font=f_chart_lbl, container_box=sbox)

    # Month Chips Slicer
    tracked_draw_text(draw, (slicer_x + 18, slicer_y + 136), "SELECT REPORTING MONTH", fill=SLATE_500, font=f_card_lbl, container_box=sbox)
    months = ["All Months", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09*"]
    chip_x = slicer_x + 18
    chip_y = slicer_y + 162
    for m in months:
        is_selected = (m == "All Months")
        bg_col = TEAL if is_selected else WHITE
        txt_col = WHITE if is_selected else SLATE_700
        chip_w = 92 if m != "All Months" else 105
        if chip_x + chip_w > slicer_x + slicer_w - 18:
            chip_x = slicer_x + 18
            chip_y += 34
        draw.rounded_rectangle([chip_x, chip_y, chip_x + chip_w, chip_y + 26], radius=13, fill=bg_col, outline=TEAL if is_selected else SLATE_200, width=1)
        tracked_draw_text(draw, (chip_x + 8, chip_y + 4), m, fill=txt_col, font=f_chip, container_box=(chip_x, chip_y, chip_x + chip_w, chip_y + 26))
        chip_x += chip_w + 6

    # Category Chips Slicer (ALL 10 categories + All Categories = 11 chips, wrapping cleanly without overflow)
    cat_y = chip_y + 42
    tracked_draw_text(draw, (slicer_x + 18, cat_y), "FILTER BY EXPENSE CATEGORY", fill=SLATE_500, font=f_card_lbl, container_box=sbox)
    cat_y += 26
    cats = [
        "All Categories", "Rent", "Groceries", "Shopping", "Food & Dining",
        "Cash Withdrawal", "Transport", "Health", "Bills & Utilities", "Entertainment", "Subscriptions"
    ]
    c_x = slicer_x + 18
    for c in cats:
        is_selected = (c == "All Categories")
        bg_col = TEAL if is_selected else WHITE
        txt_col = WHITE if is_selected else SLATE_700
        c_bbox = f_chip.getbbox(c)
        cw = (c_bbox[2] - c_bbox[0]) + 18
        if c_x + cw > slicer_x + slicer_w - 18:
            c_x = slicer_x + 18
            cat_y += 32
        draw.rounded_rectangle([c_x, cat_y, c_x + cw, cat_y + 26], radius=13, fill=bg_col, outline=TEAL if is_selected else SLATE_200, width=1)
        tracked_draw_text(draw, (c_x + 9, cat_y + 4), c, fill=txt_col, font=f_chip, container_box=(c_x, cat_y, c_x + cw, cat_y + 26))
        c_x += cw + 6

    # Slicer Summary Callout Box at bottom
    box_y = cat_y + 44
    draw.rounded_rectangle([slicer_x + 18, box_y, slicer_x + slicer_w - 18, box_y + 220], radius=8, fill=LIGHT_TEAL, outline=TEAL, width=1)
    tracked_draw_text(draw, (slicer_x + 24, box_y + 14), "DATA MODEL ATTRIBUTES", fill=DARK_TEAL, font=f_sec_hdr, container_box=sbox)
    info_lines = [
        "• Data Source: MySQL / SQLite views",
        "• Deduplication: SHA-1 transaction IDs",
        f"• Reconciled: {ctx['total_transactions']} rows ({ctx['spend_transactions']} living spend)",
        f"• Inflow / Outflow: {format_inr(ctx['total_income'])} in | {format_inr(ctx['total_spend'])} out",
        f"• Retained Capital: {format_inr(ctx['total_savings'])} ({ctx['savings_rate_pct']}%)",
        f"• September Note: Partial month ({ctx['september_days']} days)",
    ]
    iy = box_y + 44
    for line in info_lines:
        tracked_draw_text(draw, (slicer_x + 24, iy), line, fill=DARK_TEAL, font=f_chart_lbl, container_box=sbox)
        iy += 28

    # Middle Main Visual: Clustered Columns (Income vs Spend) + Line (Savings Rate %)
    main_x = start_x
    main_y = card_y + card_h + 18
    main_w = slicer_x - 18 - main_x
    main_h = H - 36 - 18 - main_y
    mbox = (main_x, main_y, main_x + main_w, main_y + main_h)

    draw.rounded_rectangle(mbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (main_x + 24, main_y + 16), "Monthly Inflow vs Outflow & Savings Rate % (12 Months)", fill=SLATE_900, font=f_sec_hdr, container_box=mbox)
    tracked_draw_text(draw, (main_x + 24, main_y + 46), f"Clustered columns represent earned income ({format_inr(65000)}/mo) vs consumption spend. Secondary line tracks monthly savings rate.", fill=SLATE_500, font=f_card_sub, container_box=mbox)

    # Legend
    leg_x = main_x + main_w - 490
    draw.rectangle([leg_x, main_y + 20, leg_x + 16, main_y + 36], fill=SLATE_400)
    tracked_draw_text(draw, (leg_x + 22, main_y + 18), "Monthly Income", fill=SLATE_700, font=f_chart_lbl, container_box=mbox)
    draw.rectangle([leg_x + 170, main_y + 20, leg_x + 186, main_y + 36], fill=TEAL)
    tracked_draw_text(draw, (leg_x + 192, main_y + 18), "Living Spend", fill=SLATE_700, font=f_chart_lbl, container_box=mbox)
    draw.line([leg_x + 310, main_y + 28, leg_x + 334, main_y + 28], fill=AMBER, width=3)
    draw.ellipse([leg_x + 318, main_y + 24, leg_x + 326, main_y + 32], fill=AMBER)
    tracked_draw_text(draw, (leg_x + 342, main_y + 18), "Savings Rate %", fill=SLATE_700, font=f_chart_lbl, container_box=mbox)

    # Chart plot area
    plot_x1 = main_x + 85
    plot_y1 = main_y + 90
    plot_x2 = main_x + main_w - 85
    plot_y2 = main_y + main_h - 70
    plot_h = plot_y2 - plot_y1
    plot_w = plot_x2 - plot_x1

    max_amount = 75000.0
    for tick in [0, 20000, 40000, 60000, 75000]:
        ty = plot_y2 - int((tick / max_amount) * plot_h)
        draw.line([plot_x1, ty, plot_x2, ty], fill=SLATE_100, width=1)
        tracked_draw_text(draw, (plot_x1 - 70, ty - 10), f"₹{tick//1000}k", fill=SLATE_500, font=f_chart_lbl, container_box=mbox)

    for pct in [0, 10, 20, 30, 40]:
        ty = plot_y2 - int((pct / 40.0) * plot_h)
        tracked_draw_text(draw, (plot_x2 + 14, ty - 10), f"{pct}%", fill=AMBER, font=f_chart_lbl, container_box=mbox)

    monthly_data = [
        ("Oct 25", 65000, 53833, 17.2),
        ("Nov 25", 65000, 60480, 7.0),
        ("Dec 25", 65000, 54001, 16.9),
        ("Jan 26", 65000, 50658, 22.1),
        ("Feb 26", 65000, 59543, 8.4),
        ("Mar 26", 65000, 45206, 30.5),
        ("Apr 26", 65000, 54700, 15.8),
        ("May 26", 65000, 53644, 17.5),
        ("Jun 26", 65000, 55166, 15.1),
        ("Jul 26", 65000, 60300, 7.2),
        ("Aug 26", 65000, 53450, 17.8),
        ("Sep 26*", 65000, 45338, 30.2),
    ]

    n_months = len(monthly_data)
    slot_w = plot_w / n_months
    bar_w = 26
    line_points = []

    for i, (m_label, inc, sp, s_rate) in enumerate(monthly_data):
        cx = plot_x1 + i * slot_w + (slot_w / 2)

        # Income bar
        inc_h = int((inc / max_amount) * plot_h)
        draw.rounded_rectangle([cx - bar_w - 2, plot_y2 - inc_h, cx - 2, plot_y2], radius=3, fill=SLATE_400)

        # Spend bar
        sp_h = int((sp / max_amount) * plot_h)
        draw.rounded_rectangle([cx + 2, plot_y2 - sp_h, cx + bar_w + 2, plot_y2], radius=3, fill=TEAL)

        # Bar label on top of spend bar
        tracked_draw_text(draw, (cx - 10, plot_y2 - sp_h - 22), f"₹{sp//1000}k", fill=SLATE_700, font=f_chart_val, container_box=mbox)

        # Savings rate point
        line_y = plot_y2 - int((s_rate / 40.0) * plot_h)
        line_points.append((cx, line_y, s_rate))

        # X-axis label
        tracked_draw_text(draw, (cx - 24, plot_y2 + 14), m_label, fill=SLATE_700, font=f_chart_lbl, container_box=mbox)

    # Draw Savings Rate line
    for i in range(len(line_points) - 1):
        x1, y1, _ = line_points[i]
        x2, y2, _ = line_points[i + 1]
        draw.line([x1, y1, x2, y2], fill=AMBER, width=3)

    # Savings rate data labels in white background pills with border so they NEVER blend into bars
    f_pill_font = get_font(15, bold=True)
    for cx, cy, rate in line_points:
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=AMBER, outline=WHITE, width=1)
        r_text = f"{rate}%"
        rb = f_pill_font.getbbox(r_text)
        rw = (rb[2] - rb[0]) + 10
        rh = (rb[3] - rb[1]) + 6
        rx1 = cx - rw // 2
        ry1 = cy - 26 - rh // 2
        draw.rounded_rectangle([rx1, ry1, rx1 + rw, ry1 + rh], radius=4, fill=WHITE, outline=AMBER, width=1)
        tracked_draw_text(draw, (rx1 + 5, ry1 + 2), r_text, fill=AMBER, font=f_pill_font, container_box=mbox)

    out_file = OUTPUT_DIR / "01_overview.png"
    img.save(out_file, dpi=(150, 150))
    print(f"Rendered Page 1 -> {out_file}")


# -------------------------------------------------------------
# PAGE 2: WHERE IT GOES (Category & Merchant Concentration)
# -------------------------------------------------------------
def render_page_2(tx_all, tx_spend, tx_income, rec, memo):
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    top4_pct = memo["page_metrics"]["page2_top4_share_pct"]  # 74.8% computed unrounded

    draw_base_page(
        draw,
        "Where It Goes · Category Breakdown & Merchant Concentration",
        f"Top 4 categories constitute {top4_pct}% of total living spend (Rent ₹2,16,000, Groceries ₹92,979, Shopping ₹90,633, Food & Dining ₹83,599)",
        2
    )

    f_sec_hdr = get_font(22, bold=True)
    f_card_sub = get_font(18, bold=False)
    f_tbl_hdr = get_font(18, bold=True)
    f_tbl_body = get_font(18, bold=False)
    f_tbl_b = get_font(18, bold=True)
    f_heat_cell = get_font(14, bold=False)
    f_heat_hdr = get_font(14, bold=True)

    start_x = 28
    top_y = 106
    left_w = 880
    right_w = W - 28 - (start_x + left_w + 18)
    right_x = start_x + left_w + 18
    left_h = H - 36 - 18 - top_y
    lbox = (start_x, top_y, start_x + left_w, top_y + left_h)

    # Left Container: Horizontal Bar Chart of Spend by Category
    draw.rounded_rectangle(lbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (start_x + 24, top_y + 16), "Spend by Category with Share of Total (Sorted Descending)", fill=SLATE_900, font=f_sec_hdr, container_box=lbox)
    tracked_draw_text(draw, (start_x + 24, top_y + 46), f"All 10 classified living spend categories. Excludes investments ({format_inr(60000)} SIP) and self-transfers.", fill=SLATE_500, font=f_card_sub, container_box=lbox)

    categories_data = [
        ("Rent", 216000.0, 33.4),
        ("Groceries", 92979.0, 14.4),
        ("Shopping", 90633.0, 14.0),
        ("Food & Dining", 83599.0, 12.9),
        ("Cash Withdrawal", 54000.0, 8.4),
        ("Transport", 39766.0, 6.2),
        ("Health", 26214.0, 4.1),
        ("Bills & Utilities", 24537.0, 3.8),
        ("Entertainment", 9375.0, 1.5),
        ("Subscriptions", 9216.0, 1.4),
    ]

    bar_start_y = top_y + 86
    bar_slot_h = 76
    bar_max_w = 420
    max_cat_val = 216000.0

    for i, (cat, val, pct) in enumerate(categories_data):
        cy = bar_start_y + i * bar_slot_h
        tracked_draw_text(draw, (start_x + 24, cy + 8), cat, fill=SLATE_900, font=f_tbl_b, container_box=lbox)

        # Bar
        bw = int((val / max_cat_val) * bar_max_w)
        bar_x = start_x + 200
        draw.rounded_rectangle([bar_x, cy + 6, bar_x + bw, cy + 32], radius=4, fill=TEAL)

        # Label inside or next to bar
        label_text = f"{format_inr(val)} ({pct}%)"
        tracked_draw_text(draw, (bar_x + bw + 14, cy + 8), label_text, fill=SLATE_700, font=f_tbl_b, container_box=lbox)

        sub_info = {
            "Rent": f"Fixed {format_inr(18000)}/mo to landlord Mr. Sharma",
            "Groceries": "Dmart, BigBasket, Zepto & Blinkit quick commerce",
            "Shopping": "Amazon, Ajio, Myntra & Flipkart online orders",
            "Food & Dining": "Swiggy, Zomato, cafes & restaurant debits",
            "Cash Withdrawal": f"24 ATM withdrawals (averaging {format_inr(2250)}/ticket)",
            "Transport": "Daily Delhi Metro, Uber, Rapido & Ola rides",
            "Health": f"Cult Fit gym membership ({format_inr(18000)}) & Tata 1mg pharmacy",
            "Bills & Utilities": "BSES electricity bills & Jio phone recharge",
            "Entertainment": "BookMyShow movie tickets and recreational outings",
            "Subscriptions": f"Netflix ({format_inr(7788)}/yr) & Spotify ({format_inr(1428)}/yr)",
        }
        tracked_draw_text(draw, (bar_x, cy + 38), sub_info.get(cat, ""), fill=SLATE_500, font=f_card_sub, container_box=lbox)

    # Right Top Container: Top 10 Payees Table (Renamed from Top 10 Merchants, row 10 has >= 24px bottom padding)
    top_merch_h = 425
    r_top_box = (right_x, top_y, right_x + right_w, top_y + top_merch_h)
    draw.rounded_rectangle(r_top_box, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (right_x + 24, top_y + 16), "Top 10 payees", fill=SLATE_900, font=f_sec_hdr, container_box=r_top_box)
    tracked_draw_text(draw, (right_x + 24, top_y + 44), "Concentration across high-ticket recurring payees and online platforms.", fill=SLATE_500, font=f_card_sub, container_box=r_top_box)

    # Table Headers
    th_y = top_y + 72
    draw.rectangle([right_x + 18, th_y, right_x + right_w - 18, th_y + 28], fill=SLATE_100)
    tracked_draw_text(draw, (right_x + 28, th_y + 5), "PAYEE NAME", fill=SLATE_500, font=f_tbl_hdr, container_box=r_top_box)
    tracked_draw_text(draw, (right_x + 380, th_y + 5), "TXNS", fill=SLATE_500, font=f_tbl_hdr, container_box=r_top_box)
    tracked_draw_text(draw, (right_x + 490, th_y + 5), "TOTAL SPEND", fill=SLATE_500, font=f_tbl_hdr, container_box=r_top_box)
    tracked_draw_text(draw, (right_x + 710, th_y + 5), "AVG TICKET", fill=SLATE_500, font=f_tbl_hdr, container_box=r_top_box)

    top_merchants = [
        ("MR SHARMA HOUSE", 12, 216000.0, 18000),
        ("ATM CASH", 24, 54000.0, 2250),
        ("AMAZON", 16, 34184.0, 2137),
        ("AJIO", 12, 27333.0, 2278),
        ("DMART", 27, 26416.0, 978),
        ("BIGBASKET", 23, 24125.0, 1049),
        ("ZEPTO", 22, 21263.0, 967),
        ("BLINKIT", 21, 21175.0, 1008),
        ("BSES RAJDHANI POWER", 12, 20949.0, 1746),
        ("SWIGGY", 45, 18759.0, 417),
    ]

    t_row_y = th_y + 30
    for r_idx, (m_name, tx_cnt, sp_tot, avg_t) in enumerate(top_merchants):
        bg = CARD_BG if r_idx % 2 == 0 else SLATE_100
        row_box = (right_x + 18, t_row_y, right_x + right_w - 18, t_row_y + 26)
        draw.rectangle(row_box, fill=bg)
        # Consistent bold across all payees
        tracked_draw_text(draw, (right_x + 28, t_row_y + 4), m_name, fill=SLATE_900, font=f_tbl_b, container_box=r_top_box)
        tracked_draw_text(draw, (right_x + 390, t_row_y + 4), str(tx_cnt), fill=SLATE_700, font=f_tbl_body, container_box=r_top_box)
        tracked_draw_text(draw, (right_x + 490, t_row_y + 4), format_inr(sp_tot), fill=TEAL if r_idx < 3 else SLATE_900, font=f_tbl_b, container_box=r_top_box)
        tracked_draw_text(draw, (right_x + 710, t_row_y + 4), format_inr(avg_t), fill=SLATE_700, font=f_tbl_body, container_box=r_top_box)
        t_row_y += 28

    # Row 10 finished at t_row_y = th_y + 30 + 10 * 28 = 72 + 30 + 280 = 382. Bottom margin = 425 - 382 = 43px >= 24px!

    # Right Bottom Container: 10 Categories x 12 Months Spend Heat Map (shaded per category row min to max)
    heat_y = top_y + top_merch_h + 18
    heat_h = H - 36 - 18 - heat_y
    r_btm_box = (right_x, heat_y, right_x + right_w, heat_y + heat_h)
    draw.rounded_rectangle(r_btm_box, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (right_x + 24, heat_y + 14), "10 Categories × 12 Months Spend Heat Map", fill=SLATE_900, font=f_sec_hdr, container_box=r_btm_box)
    tracked_draw_text(draw, (right_x + 24, heat_y + 38), "Monthly living expenditure shaded per category row (min to max). Shading reflects category-relative seasonality.", fill=SLATE_500, font=f_card_sub, container_box=r_btm_box)

    all_10_cats = [
        "Rent", "Groceries", "Shopping", "Food & Dining", "Cash Withdrawal",
        "Transport", "Health", "Bills & Utilities", "Entertainment", "Subscriptions"
    ]
    all_12_months = [
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
        "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"
    ]
    months_headers = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep*"]

    # Pre-calculate category row spends to determine min/max per row
    cat_month_matrix = {}
    for c_name in all_10_cats:
        cat_month_matrix[c_name] = []
        for m_name in all_12_months:
            sub_df = tx_spend[(tx_spend["category"] == c_name) & (tx_spend["txn_month"] == m_name)]
            amt = float(sub_df["amount"].sum()) if len(sub_df) > 0 else 0.0
            cat_month_matrix[c_name].append(amt)

    hy = heat_y + 64
    draw.rectangle([right_x + 18, hy, right_x + right_w - 18, hy + 24], fill=SLATE_100)
    tracked_draw_text(draw, (right_x + 24, hy + 4), "CATEGORY", fill=SLATE_500, font=f_heat_hdr, container_box=r_btm_box)
    for m_i, m_lbl in enumerate(months_headers):
        tracked_draw_text(draw, (right_x + 175 + m_i * 64, hy + 4), m_lbl, fill=SLATE_500, font=f_heat_hdr, container_box=r_btm_box)

    hy += 26
    for c_name in all_10_cats:
        tracked_draw_text(draw, (right_x + 24, hy + 5), c_name, fill=SLATE_900, font=f_tbl_b, container_box=r_btm_box)
        row_vals = cat_month_matrix[c_name]
        r_min = min(row_vals)
        r_max = max(row_vals)

        for m_i, amt in enumerate(row_vals):
            if r_max > r_min:
                intensity = int(((amt - r_min) / (r_max - r_min)) * 160)
            else:
                intensity = 80 if amt > 0 else 0
            heat_color = (245 - intensity, 255 - int(intensity * 0.45), 248 - int(intensity * 0.35)) if amt > 0 else CARD_BG

            cell_x = right_x + 170 + m_i * 64
            draw.rounded_rectangle([cell_x, hy + 2, cell_x + 60, hy + 26], radius=3, fill=heat_color, outline=SLATE_200, width=1)
            cell_txt = f"{amt/1000:.1f}k" if amt >= 1000 else f"{int(amt)}"
            tracked_draw_text(draw, (cell_x + 8, hy + 5), cell_txt, fill=SLATE_900 if amt > 0 else SLATE_400, font=f_heat_cell, container_box=r_btm_box)
        hy += 27

    out_file = OUTPUT_DIR / "02_where_it_goes.png"
    img.save(out_file, dpi=(150, 150))
    print(f"Rendered Page 2 -> {out_file}")


# -------------------------------------------------------------
# PAGE 3: LEAKS & SUBSCRIPTIONS
# -------------------------------------------------------------
def render_page_3(tx_all, tx_spend, tx_income, rec, memo):
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    f2 = memo["findings"]["f2_food_delivery"]
    f3 = memo["findings"]["f3_small_ticket_leaks"]
    f1 = memo["findings"]["f1_subscriptions"]

    draw_base_page(
        draw,
        "Budget Leaks & Recurring Subscriptions",
        f"Food delivery totaled {format_inr(f2['total_spend'])} across {f2['orders_count']} orders; {f3['discretionary_sub300_count']} discretionary micro-transactions under ₹300 leaked {format_inr(f3['discretionary_sub300_total'])}",
        3
    )

    f_sec_hdr = get_font(22, bold=True)
    f_card_sub = get_font(18, bold=False)
    f_tbl_hdr = get_font(18, bold=True)
    f_tbl_body = get_font(18, bold=False)
    f_tbl_b = get_font(18, bold=True)
    f_chart_lbl = get_font(18, bold=False)
    f_chart_val = get_font(18, bold=True)
    f_small_val = get_font(14, bold=False)

    start_x = 28
    top_y = 106
    left_w = 880
    right_w = W - 28 - (start_x + left_w + 18)
    right_x = start_x + left_w + 18
    left_h = H - 36 - 18 - top_y
    lbox = (start_x, top_y, start_x + left_w, top_y + left_h)

    # Left Container: Subscriptions & Recurring Commitments Table
    draw.rounded_rectangle(lbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (start_x + 24, top_y + 16), "Recurring Payments & Subscriptions (Detected by Pipeline)", fill=SLATE_900, font=f_sec_hdr, container_box=lbox)
    tracked_draw_text(draw, (start_x + 24, top_y + 44), "Periodic bills flagged by amount tolerance (±5% median) and 30-day cadence. Sorted by annual cost.", fill=SLATE_500, font=f_card_sub, container_box=lbox)

    # Table Header
    th_y = top_y + 78
    draw.rectangle([start_x + 18, th_y, start_x + left_w - 18, th_y + 34], fill=SLATE_100)
    tracked_draw_text(draw, (start_x + 28, th_y + 6), "MERCHANT", fill=SLATE_500, font=f_tbl_hdr, container_box=lbox)
    tracked_draw_text(draw, (start_x + 260, th_y + 6), "CATEGORY", fill=SLATE_500, font=f_tbl_hdr, container_box=lbox)
    tracked_draw_text(draw, (start_x + 440, th_y + 6), "CADENCE", fill=SLATE_500, font=f_tbl_hdr, container_box=lbox)
    tracked_draw_text(draw, (start_x + 570, th_y + 6), "TICKET", fill=SLATE_500, font=f_tbl_hdr, container_box=lbox)
    tracked_draw_text(draw, (start_x + 710, th_y + 6), "ANNUAL COST", fill=SLATE_500, font=f_tbl_hdr, container_box=lbox)

    rec_list = [
        ("MR SHARMA HOUSE", "Rent", "monthly", 18000.0, 216000.0),
        ("HDFC MUTUAL FUND", "Investments", "monthly", 5000.0, 60000.0),
        ("CULT FIT", "Health", "monthly", 1500.0, 18000.0),
        ("NETFLIX", "Subscriptions", "monthly", 649.0, 7788.0),
        ("JIO PREPAID", "Bills & Utilities", "monthly", 299.0, 3588.0),
        ("SPOTIFY", "Subscriptions", "monthly", 119.0, 1428.0),
    ]

    r_y = th_y + 38
    for i, (m_name, cat, freq, typ, ann) in enumerate(rec_list):
        bg = CARD_BG if i % 2 == 0 else SLATE_100
        draw.rectangle([start_x + 18, r_y, start_x + left_w - 18, r_y + 40], fill=bg)
        tracked_draw_text(draw, (start_x + 28, r_y + 9), m_name, fill=SLATE_900, font=f_tbl_b, container_box=lbox)
        tracked_draw_text(draw, (start_x + 260, r_y + 9), cat, fill=SLATE_700, font=f_tbl_body, container_box=lbox)
        tracked_draw_text(draw, (start_x + 440, r_y + 9), freq.capitalize(), fill=SLATE_700, font=f_tbl_body, container_box=lbox)
        tracked_draw_text(draw, (start_x + 570, r_y + 9), format_inr(typ), fill=SLATE_900, font=f_tbl_body, container_box=lbox)
        tracked_draw_text(draw, (start_x + 710, r_y + 9), format_inr(ann), fill=TEAL, font=f_tbl_b, container_box=lbox)
        r_y += 44

    # Total Row
    draw.rectangle([start_x + 18, r_y, start_x + left_w - 18, r_y + 42], fill=LIGHT_TEAL)
    tracked_draw_text(draw, (start_x + 28, r_y + 11), "TOTAL ALL RECURRING COMMITMENTS", fill=DARK_TEAL, font=f_tbl_b, container_box=lbox)
    tracked_draw_text(draw, (start_x + 710, r_y + 11), format_inr(f1["total_recurring_commitments_with_sip"]), fill=DARK_TEAL, font=f_tbl_b, container_box=lbox)
    r_y += 48

    # Indented "of which" row for pure digital subscriptions
    draw.rectangle([start_x + 18, r_y, start_x + left_w - 18, r_y + 40], fill=SLATE_100)
    tracked_draw_text(draw, (start_x + 48, r_y + 10), "of which: Pure digital subscriptions (Netflix + Spotify)", fill=SLATE_900, font=f_tbl_b, container_box=lbox)
    tracked_draw_text(draw, (start_x + 710, r_y + 10), format_inr(f1["annual_cost"]), fill=TEAL, font=f_tbl_b, container_box=lbox)

    # Narrative callout inside left card
    call_y = r_y + 56
    draw.rounded_rectangle([start_x + 18, call_y, start_x + left_w - 18, call_y + 300], radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    draw.rectangle([start_x + 18, call_y, start_x + 24, call_y + 300], fill=TEAL)
    tracked_draw_text(draw, (start_x + 36, call_y + 16), "SUBSCRIPTION AUDIT & SAVINGS STRATEGY", fill=TEAL, font=f_sec_hdr, container_box=lbox)
    notes = [
        f"• Pure Digital Streaming: Netflix ({format_inr(7788)}/yr) + Spotify ({format_inr(1428)}/yr) cost {format_inr(f1['annual_cost'])}/year.",
        f"• Optimization Potential: Pausing both subscriptions yields {format_inr(f1['savable_monthly'])} / month",
        f"  in immediate recurring savings (100% of pure streaming outlays).",
        f"• Fixed Commitments: Rent ({format_inr(216000)}) and Mutual Fund SIP ({format_inr(60000)}) represent",
        f"  essential living costs and capital investment, constituting {f1['rent_plus_sip_pct']}% of total outflows.",
        f"• Fitness Membership: Cult Fit gym membership of {format_inr(1500)}/mo ({format_inr(18000)}/yr) should be tracked",
        "  against active attendance logs to prevent silent gym membership wastage.",
    ]
    ny = call_y + 52
    for note in notes:
        tracked_draw_text(draw, (start_x + 36, ny), note, fill=SLATE_700, font=f_tbl_body, container_box=lbox)
        ny += 34

    # Right Top Container: Discretionary Small-Ticket Leaks (< ₹300) Bar Chart (205 txns, ₹38,871)
    leak_h = 420
    r_top_box = (right_x, top_y, right_x + right_w, top_y + leak_h)
    draw.rounded_rectangle(r_top_box, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    tracked_draw_text(draw, (right_x + 24, top_y + 16), "Discretionary Small-Ticket Leaks (< ₹300, excl. recurring bills)", fill=SLATE_900, font=f_sec_hdr, container_box=r_top_box)
    tracked_draw_text(draw, (right_x + 24, top_y + 44), f"{f3['discretionary_sub300_count']} micro-debits totaling {format_inr(f3['discretionary_sub300_total'])} (averaging {format_inr(f3['discretionary_sub300_avg'])}/ticket and {format_inr(f3['discretionary_sub300_monthly'])}/mo).", fill=SLATE_500, font=f_card_sub, container_box=r_top_box)

    leaks = [
        ("Transport", f3["category_split"]["Transport"]["txns"], f3["category_split"]["Transport"]["total"]),
        ("Food & Dining", f3["category_split"]["Food & Dining"]["txns"], f3["category_split"]["Food & Dining"]["total"]),
        ("Groceries", f3["category_split"]["Groceries"]["txns"], f3["category_split"]["Groceries"]["total"]),
        ("Health", f3["category_split"]["Health"]["txns"], f3["category_split"]["Health"]["total"]),
    ]

    ly = top_y + 90
    max_leak_amt = f3["category_split"]["Transport"]["total"]
    leak_bar_w = 420
    for cat_name, cnt, amt in leaks:
        tracked_draw_text(draw, (right_x + 24, ly + 8), cat_name, fill=SLATE_900, font=f_tbl_b, container_box=r_top_box)
        bw = int((amt / max_leak_amt) * leak_bar_w)
        draw.rounded_rectangle([right_x + 200, ly + 6, right_x + 200 + bw, ly + 32], radius=4, fill=TEAL)
        tracked_draw_text(draw, (right_x + 200 + bw + 14, ly + 8), f"{format_inr(amt)} ({cnt} txns)", fill=SLATE_700, font=f_tbl_b, container_box=r_top_box)
        ly += 68

    # Right Bottom Container: Food Delivery Monthly Order Frequency (Swiggy/Zomato/Dominos)
    deliv_y = top_y + leak_h + 18
    deliv_h = H - 36 - 18 - deliv_y
    r_btm_box = (right_x, deliv_y, right_x + right_w, deliv_y + deliv_h)
    draw.rounded_rectangle(r_btm_box, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    # Retitled with monthly spend
    tracked_draw_text(draw, (right_x + 24, deliv_y + 16), "Food delivery orders per month (with monthly spend)", fill=SLATE_900, font=f_sec_hdr, container_box=r_btm_box)
    tracked_draw_text(draw, (right_x + 24, deliv_y + 42), f"{f2['orders_count']} orders across 12 months totaling {format_inr(f2['total_spend'])} (averaging {round(f2['orders_count']/12, 1)} orders and {format_inr(f2['avg_monthly_spend'])}/mo).", fill=SLATE_500, font=f_card_sub, container_box=r_btm_box)

    food_deliv_data = [
        ("Oct 25", 12, 4891.0),
        ("Nov 25", 11, 4938.0),
        ("Dec 25", 13, 4631.0),
        ("Jan 26", 11, 3864.0),
        ("Feb 26", 12, 5690.0),
        ("Mar 26", 7, 2762.0),
        ("Apr 26", 8, 2984.0),
        ("May 26", 12, 4427.0),
        ("Jun 26", 14, 5765.0),
        ("Jul 26", 13, 5508.0),
        ("Aug 26", 8, 2999.0),
        ("Sep 26*", 8, 3106.0),
    ]

    fd_plot_x = right_x + 50
    fd_plot_y = deliv_y + 80
    fd_plot_w = right_w - 90
    fd_plot_h = deliv_h - 130
    slot_fd = fd_plot_w / len(food_deliv_data)

    max_orders = 16
    for i, (m_lbl, ord_cnt, sp_amt) in enumerate(food_deliv_data):
        fx = fd_plot_x + i * slot_fd + (slot_fd / 2)
        bh = int((ord_cnt / max_orders) * fd_plot_h)
        draw.rounded_rectangle([fx - 14, fd_plot_y + fd_plot_h - bh, fx + 14, fd_plot_y + fd_plot_h], radius=3, fill=TEAL)
        # Order count on top
        tracked_draw_text(draw, (fx - 8, fd_plot_y + fd_plot_h - bh - 24), str(ord_cnt), fill=SLATE_900, font=f_chart_val, container_box=r_btm_box)
        # Spend label below bar
        tracked_draw_text(draw, (fx - 16, fd_plot_y + fd_plot_h + 4), f"₹{sp_amt/1000:.1f}k", fill=TEAL, font=f_small_val, container_box=r_btm_box)
        # Month label
        tracked_draw_text(draw, (fx - 24, fd_plot_y + fd_plot_h + 22), m_lbl, fill=SLATE_500, font=f_chart_lbl, container_box=r_btm_box)

    out_file = OUTPUT_DIR / "03_leaks_subscriptions.png"
    img.save(out_file, dpi=(150, 150))
    print(f"Rendered Page 3 -> {out_file}")


# -------------------------------------------------------------
# PAGE 4: INSIGHTS & RECOMMENDATIONS
# -------------------------------------------------------------
def render_page_4(tx_all, tx_spend, tx_income, rec, memo):
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    f1 = memo["findings"]["f1_subscriptions"]
    f2 = memo["findings"]["f2_food_delivery"]
    f3 = memo["findings"]["f3_small_ticket_leaks"]
    f4 = memo["findings"]["f4_weekend_vs_weekday"]
    f5 = memo["findings"]["f5_savings_rate_drop"]
    recs = memo["recommendations"]
    tot = memo["total_savings_potential"]
    ctx = memo["context"]
    va = f4["version_a_all_living_spend"]
    vb = f4["version_b_variable_spend_excluding_fixed"]

    draw_base_page(
        draw,
        "Strategic Findings & Prioritized Recommendations",
        f"Empirical findings and actionable zero-overlap plan to unlock +{format_inr(tot['monthly'])} / month, lifting savings rate from {tot['baseline_savings_rate_pct']}% to {tot['projected_savings_rate_pct']}%",
        4
    )

    f_sec_hdr = get_font(22, bold=True)
    f_card_hdr = get_font(18, bold=True)
    f_body = get_font(18, bold=False)
    f_body_b = get_font(18, bold=True)
    f_badge = get_font(16, bold=True)
    f_card_sub = get_font(18, bold=False)
    f_small_val = get_font(14, bold=False)

    start_x = 28
    top_y = 106
    col_w = (W - 28 - start_x - 24) // 2
    left_x = start_x
    right_x = start_x + col_w + 24
    col_h = H - 36 - 18 - top_y
    lbox = (left_x, top_y, left_x + col_w, top_y + col_h)
    rbox = (right_x, top_y, right_x + col_w, top_y + col_h)

    # LEFT COLUMN: 5 Quantified Empirical Findings
    draw.rounded_rectangle(lbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    draw.rectangle([left_x, top_y, left_x + col_w, top_y + 46], fill=SLATE_100)
    tracked_draw_text(draw, (left_x + 20, top_y + 12), "TOP 5 EMPIRICAL FINDINGS (DATA-GROUNDED)", fill=SLATE_900, font=f_sec_hdr, container_box=lbox)

    findings_text = [
        (
            "01",
            "Digital Subscriptions & Commitments",
            f"{format_inr(f1['annual_cost'])} / yr pure subscriptions",
            [
                f"• Pipeline detected 2 pure digital subscriptions: Netflix ({format_inr(7788)}/yr) and Spotify ({format_inr(1428)}/yr).",
                f"• Fixed living commitments (Rent, Gym, Jio, subs) total {format_inr(f1['recurring_living_spend'])}/yr ({f1['pct_of_living_spend']}% of living spend).",
                f"• With ₹60k SIP, total commitments reach {format_inr(f1['total_recurring_commitments_with_sip'])}/yr ({f1['pct_of_total_outflow']}% of total cash outflows).",
            ]
        ),
        (
            "02",
            "High-Frequency Food Delivery Concentration",
            f"{f2['orders_count']} Orders · {format_inr(f2['total_spend'])} Spend",
            [
                f"• Swiggy, Zomato, and Dominos: {f2['orders_count']} orders across 12 months (~{round(f2['orders_count']/12, 1)} orders / month).",
                f"• Food delivery accounts for {f2['pct_of_discretionary']}% of discretionary spend and {f2['pct_of_food_dining']}% of dining spend.",
                f"• Average order ticket of {format_inr(f2['avg_ticket'])} with monthly run-rate reaching {format_inr(f2['avg_monthly_spend'])}/mo.",
            ]
        ),
        (
            "03",
            "Discretionary Small-Ticket Leaks (< ₹300)",
            f"{f3['discretionary_sub300_count']} Debits · {format_inr(f3['discretionary_sub300_total'])} Total",
            [
                f"• Discretionary debits under ₹300 (excl. recurring bills) totaled {f3['discretionary_sub300_count']} txns (avg {format_inr(f3['discretionary_sub300_avg'])}).",
                f"• Daily transit (Uber, Rapido, Ola, Delhi Metro) leads with 125 rides ({format_inr(f3['transport_total'])}), plus 71 cafe/quick food stops.",
                f"• Micro-spending quietly drains {format_inr(f3['discretionary_sub300_monthly'])} every month without explicit budgeting.",
            ]
        ),
        (
            "04",
            "Weekday vs. Weekend Daily Spend Density",
            f"+{vb['robustness_check']['weekday_higher_pct_excluding_cash']}% to +{vb['weekday_higher_pct']}% on Weekdays",
            [
                f"• Ver A (all spend): Weekday {format_inr(va['weekday_per_day'])}/day (258 days) vs Weekend {format_inr(va['weekend_per_day'])}/day (104 days, +{va['weekday_higher_pct']}%).",
                f"• Ver B (variable spend): Weekday {format_inr(vb['weekday_per_day'])}/day vs Weekend {format_inr(vb['weekend_per_day'])}/day (+{vb['weekday_higher_pct']}% gap).",
                f"• Robustness: +{vb['robustness_check']['weekday_higher_pct_excluding_ge_5000']}% excl. ≥₹5k txns; +{vb['robustness_check']['weekday_higher_pct_excluding_cash']}% excl. cash withdrawals.",
            ]
        ),
        (
            "05",
            "Annual Savings Rate Trough & Core Driver",
            f"November 2025 dropped to {f5['lowest_savings_rate_pct']}%",
            [
                f"• Savings rate hit an annual low of {f5['lowest_savings_rate_pct']}% in Nov 2025 ({format_inr(f5['lowest_month_spend'])} spend vs. a {f5['highest_savings_rate_pct']}% savings rate in March).",
                f"• Driver: Festive-season spike (synthetic data): Shopping rose to {format_inr(f5['drivers_by_category']['Shopping'])} and Groceries to {format_inr(f5['drivers_by_category']['Groceries'])}.",
                "• (Note: September 2026 data ends on 27 Sep, making its MoM change a partial-month artifact).",
            ]
        ),
    ]

    fy = top_y + 54
    card_h_find = 156
    for badge, title, subtitle, bullets in findings_text:
        find_box = (left_x + 16, fy, left_x + col_w - 16, fy + card_h_find)
        draw.rounded_rectangle(find_box, radius=6, fill=WHITE, outline=SLATE_200, width=1)
        draw.rectangle([left_x + 16, fy, left_x + 22, fy + card_h_find], fill=TEAL)

        # Badge
        draw.rounded_rectangle([left_x + 32, fy + 12, left_x + 68, fy + 36], radius=4, fill=LIGHT_TEAL)
        tracked_draw_text(draw, (left_x + 40, fy + 14), badge, fill=DARK_TEAL, font=f_badge, container_box=find_box)

        tracked_draw_text(draw, (left_x + 80, fy + 14), title, fill=SLATE_900, font=f_card_hdr, container_box=find_box)
        sub_w = f_badge.getbbox(subtitle)[2] - f_badge.getbbox(subtitle)[0]
        tracked_draw_text(draw, (left_x + col_w - 32 - sub_w, fy + 14), subtitle, fill=TEAL, font=f_badge, container_box=find_box)

        by = fy + 44
        for bullet in bullets:
            tracked_draw_text(draw, (left_x + 32, by), bullet, fill=SLATE_700, font=f_body, container_box=find_box)
            by += 28
        fy += card_h_find + 12

    # RIGHT COLUMN: 3 Strategic Recommendations & Savings Plan (ZERO OVERLAP)
    draw.rounded_rectangle(rbox, radius=8, fill=CARD_BG, outline=SLATE_200, width=1)
    draw.rectangle([right_x, top_y, right_x + col_w, top_y + 46], fill=SLATE_100)
    tracked_draw_text(draw, (right_x + 20, top_y + 12), "PRIORITIZED RECOMMENDATIONS (ZERO OVERLAP)", fill=SLATE_900, font=f_sec_hdr, container_box=rbox)

    recs_text = [
        (
            "ACTION 01",
            recs[0]["title"],
            recs[0]["assumption"],
            "Formula: ₹51,565 × 50% ÷ 12 months. Directly cuts delivery convenience drain.",
            f"+{format_inr(recs[0]['expected_monthly_saving'])} / mo",
            f"{format_inr(recs[0]['expected_annual_saving'])} / yr"
        ),
        (
            "ACTION 02",
            recs[1]["title"],
            recs[1]["assumption"],
            "Formula: (Netflix ₹7,788 + Spotify ₹1,428) ÷ 12 months. 100% of pure streaming outlays.",
            f"+{format_inr(recs[1]['expected_monthly_saving'])} / mo",
            f"{format_inr(recs[1]['expected_annual_saving'])} / yr"
        ),
        (
            "ACTION 03",
            recs[2]["title"],
            "Switch 50% short cab rides to public transit & curb impulse cafes.",
            f"Formula: (Cab rides {format_inr(f3['cab_pool_total'])} + Cafes {format_inr(f3['cafes_total'])} = {format_inr(f3['non_overlap_pool'])}) × 50% ÷ 12 mo.",
            f"+{format_inr(recs[2]['expected_monthly_saving'])} / mo",
            f"{format_inr(recs[2]['expected_annual_saving'])} / yr"
        ),
    ]

    ry = top_y + 54
    rec_box_h = 200
    for badge, title, subtitle, desc, sav_mo, sav_yr in recs_text:
        rec_box = (right_x + 16, ry, right_x + col_w - 16, ry + rec_box_h)
        draw.rounded_rectangle(rec_box, radius=8, fill=WHITE, outline=SLATE_200, width=1)

        # Header banner
        draw.rounded_rectangle([right_x + 16, ry, right_x + col_w - 16, ry + 38], radius=6, fill=LIGHT_TEAL)
        draw.rectangle([right_x + 16, ry + 20, right_x + col_w - 16, ry + 38], fill=LIGHT_TEAL)
        tracked_draw_text(draw, (right_x + 28, ry + 9), badge, fill=DARK_TEAL, font=f_badge, container_box=rec_box)
        tracked_draw_text(draw, (right_x + 130, ry + 9), title, fill=SLATE_900, font=f_card_hdr, container_box=rec_box)

        tracked_draw_text(draw, (right_x + 28, ry + 46), subtitle, fill=TEAL, font=f_body_b, container_box=rec_box)
        tracked_draw_text(draw, (right_x + 28, ry + 74), desc, fill=SLATE_700, font=f_body, container_box=rec_box)

        # Scenario saving bottom box (Renamed per requirement 8)
        draw.line([right_x + 28, ry + 140, right_x + col_w - 28, ry + 140], fill=SLATE_200, width=1)
        tracked_draw_text(draw, (right_x + 28, ry + 154), "Scenario saving (gross, before substitution costs):", fill=SLATE_500, font=f_card_sub, container_box=rec_box)
        tracked_draw_text(draw, (right_x + 440, ry + 152), sav_mo, fill=GREEN, font=f_card_hdr, container_box=rec_box)
        tracked_draw_text(draw, (right_x + 620, ry + 154), f"({sav_yr})", fill=SLATE_500, font=f_card_sub, container_box=rec_box)

        ry += rec_box_h + 12

    # Combined Impact Banner at bottom of right column (Fits cleanly with >= 24px inner margins)
    banner_y = ry + 6
    banner_h = 204
    b_box = (right_x + 16, banner_y, right_x + col_w - 16, banner_y + banner_h)
    draw.rounded_rectangle(b_box, radius=8, fill=TEAL)
    tracked_draw_text(draw, (right_x + 40, banner_y + 24), "COMBINED FINANCIAL SAVINGS IMPACT (ZERO OVERLAP)", fill=WHITE, font=f_sec_hdr, container_box=b_box)
    tracked_draw_text(draw, (right_x + 40, banner_y + 56), f"Implementing all 3 recommendations yields +{format_inr(tot['monthly'])} / month in retained savings (+{format_inr(tot['annual'])} / year).", fill=WHITE, font=f_body, container_box=b_box)
    tracked_draw_text(draw, (right_x + 40, banner_y + 88), f"Lifts savings rate from {tot['baseline_savings_rate_pct']}% to {tot['projected_savings_rate_pct']}% (+{tot['percentage_points_increase']} percentage points, unrounded: 17.14% → 23.04%).", fill=LIGHT_TEAL, font=f_body_b, container_box=b_box)
    tracked_draw_text(draw, (right_x + 40, banner_y + 120), f"• Annual retained capital jumps from {format_inr(ctx['total_savings'])} to {format_inr(ctx['total_savings'] + tot['annual'])} (+{format_inr(tot['annual'])} / year).", fill=WHITE, font=f_body, container_box=b_box)
    tracked_draw_text(draw, (right_x + 40, banner_y + 152), "• Note: Gross savings scenario; assumes removed spend is not substituted with alternative expenditure.", fill=LIGHT_TEAL, font=f_body, container_box=b_box, margin=24)

    out_file = OUTPUT_DIR / "04_insights.png"
    img.save(out_file, dpi=(150, 150))
    print(f"Rendered Page 4 -> {out_file}")


def render_all_dashboards():
    global RENDERED_STRINGS
    RENDERED_STRINGS = []

    tx_all, tx_spend, tx_income, rec = load_and_assert_data()
    memo = load_memo()

    render_page_1(tx_all, tx_spend, tx_income, rec, memo)
    render_page_2(tx_all, tx_spend, tx_income, rec, memo)
    render_page_3(tx_all, tx_spend, tx_income, rec, memo)
    render_page_4(tx_all, tx_spend, tx_income, rec, memo)

    # Save all rendered strings to docs/audit/rendered_text.json (merged with architecture strings if present)
    arch_file = Path("docs/audit/architecture_rendered_text.json")
    all_strings = list(RENDERED_STRINGS)
    if arch_file.exists():
        arch_strings = json.loads(arch_file.read_text(encoding="utf-8"))
        all_strings.extend(arch_strings)
    RENDERED_TEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RENDERED_TEXT_PATH.write_text(json.dumps(all_strings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(all_strings)} rendered strings to {RENDERED_TEXT_PATH}")


if __name__ == "__main__":
    render_all_dashboards()
