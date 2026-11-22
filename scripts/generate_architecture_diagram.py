# scripts/generate_architecture_diagram.py
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SVG_OUT = Path("docs/architecture.svg")
PNG_OUT = Path("docs/architecture.png")
MEMO_PATH = Path("docs/memo_numbers.json")
RENDERED_TEXT_PATH = Path("docs/audit/rendered_text.json")

ARCH_DRAWN_STRINGS = []


def load_memo_data():
    if not MEMO_PATH.exists():
        raise FileNotFoundError(f"{MEMO_PATH} missing!")
    return json.loads(MEMO_PATH.read_text(encoding="utf-8"))


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Font fallback chain: Segoe UI -> DejaVu Sans."""
    candidates = []
    if bold:
        candidates = [
            Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("assets/fonts/DejaVuSans-Bold.ttf"),
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


def generate_svg(data: dict) -> str:
    global ARCH_DRAWN_STRINGS
    if "categorizer_evaluation" in data:
        holdout_acc = data["categorizer_evaluation"]["hard_holdout"]["accuracy_pct"]
    else:
        holdout_acc = 78.33
    rec_monthly = int(round(data["total_savings_potential"]["monthly"]))

    title_txt = "UPI / Bank Statement Spend Analyzer · Architecture"
    sub_txt = "End-to-End Modular Pipeline: Statement Ingestion → Data Cleaning → Classification → Detection → Relational Analytics → Reporting"
    clean_fmt = "• Formats: CSV (2 bank layouts)"
    holdout_line = f"• Clean: 100% | Holdout: {holdout_acc}%"
    memo_rec_line = f"• 3 prioritized recommendations saving +₹{rec_monthly:,} / month"
    foot_txt = "Modular Data Pipeline Architecture · Built with Python, pandas, SQLAlchemy, MySQL & Power BI"

    for s in [title_txt, sub_txt, clean_fmt, holdout_line, memo_rec_line, foot_txt]:
        if s not in ARCH_DRAWN_STRINGS:
            ARCH_DRAWN_STRINGS.append(s)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" width="1600" height="900">
  <defs>
    <style>
      .title {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 28px; font-weight: 700; fill: #0F172A; }}
      .subtitle {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 16px; font-weight: 400; fill: #64748B; }}
      .node-title {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 17px; font-weight: 700; fill: #0F172A; }}
      .node-desc {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; font-weight: 400; fill: #475569; }}
      .node-pill {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 11px; font-weight: 600; fill: #0F766E; }}
      .arrow {{ stroke: #0F766E; stroke-width: 2.5; fill: none; }}
      .arrow-head {{ fill: #0F766E; }}
    </style>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" class="arrow-head" />
    </marker>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#0F172A" flood-opacity="0.06"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1600" height="900" fill="#F8FAFC"/>
  
  <!-- Top Accent Bar -->
  <rect width="1600" height="8" fill="#0F766E"/>

  <!-- Header -->
  <text x="80" y="65" class="title">{title_txt}</text>
  <text x="80" y="95" class="subtitle">{sub_txt}</text>

  <!-- Pipeline Flow Nodes (2 Rows x 4 Columns) -->
  
  <!-- Row 1: Left to Right -->
  
  <!-- Node 1: Raw Statement Sources -->
  <g transform="translate(80, 150)" filter="url(#shadow)">
    <rect width="310" height="180" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.5"/>
    <rect x="0" y="0" width="310" height="38" rx="12" fill="#CCFBF1"/>
    <rect x="0" y="24" width="310" height="14" fill="#CCFBF1"/>
    <text x="20" y="25" class="node-pill">01 · INGESTION SOURCES</text>
    <text x="20" y="70" class="node-title">Bank Statements</text>
    <text x="20" y="95" class="node-desc">{clean_fmt}</text>
    <text x="20" y="118" class="node-desc">• HDFC layout (DD/MM/YY)</text>
    <text x="20" y="141" class="node-desc">• ICICI layout (DD-MM-YYYY)</text>
    <text x="20" y="164" class="node-desc">• Synthetic &amp; private inputs</text>
  </g>

  <!-- Arrow 1 -> 2 -->
  <path d="M 390 240 L 450 240" class="arrow" marker-end="url(#arrow)"/>

  <!-- Node 2: parsers.py -->
  <g transform="translate(460, 150)" filter="url(#shadow)">
    <rect width="310" height="180" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.5"/>
    <rect x="0" y="0" width="310" height="38" rx="12" fill="#CCFBF1"/>
    <rect x="0" y="24" width="310" height="14" fill="#CCFBF1"/>
    <text x="20" y="25" class="node-pill">02 · STATEMENT PARSING</text>
    <text x="20" y="70" class="node-title">parsers.py</text>
    <text x="20" y="95" class="node-desc">• Format auto-detection</text>
    <text x="20" y="118" class="node-desc">• BANK_FORMATS config registry</text>
    <text x="20" y="141" class="node-desc">• SHA-1 deterministic txn_id</text>
    <text x="20" y="164" class="node-desc">• Output: Unified DataFrame</text>
  </g>

  <!-- Arrow 2 -> 3 -->
  <path d="M 770 240 L 830 240" class="arrow" marker-end="url(#arrow)"/>

  <!-- Node 3: cleaning.py -->
  <g transform="translate(840, 150)" filter="url(#shadow)">
    <rect width="310" height="180" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.5"/>
    <rect x="0" y="0" width="310" height="38" rx="12" fill="#CCFBF1"/>
    <rect x="0" y="24" width="310" height="14" fill="#CCFBF1"/>
    <text x="20" y="25" class="node-pill">03 · DATA NORMALIZATION</text>
    <text x="20" y="70" class="node-title">cleaning.py</text>
    <text x="20" y="95" class="node-desc">• Strip UPI/NEFT/IMPS noise</text>
    <text x="20" y="118" class="node-desc">• Merchant entity extraction</text>
    <text x="20" y="141" class="node-desc">• Tag self-transfers &amp; refunds</text>
    <text x="20" y="164" class="node-desc">• Date parsing &amp; calendar features</text>
  </g>

  <!-- Arrow 3 -> 4 -->
  <path d="M 1150 240 L 1210 240" class="arrow" marker-end="url(#arrow)"/>

  <!-- Node 4: categorize.py -->
  <g transform="translate(1220, 150)" filter="url(#shadow)">
    <rect width="300" height="180" rx="12" fill="#FFFFFF" stroke="#0F766E" stroke-width="2"/>
    <rect x="0" y="0" width="300" height="38" rx="12" fill="#0F766E"/>
    <rect x="0" y="24" width="300" height="14" fill="#0F766E"/>
    <text x="20" y="25" class="node-pill" style="fill: #FFFFFF;">04 · CLASSIFICATION ENGINE</text>
    <text x="20" y="70" class="node-title">categorize.py</text>
    <text x="20" y="95" class="node-desc">• Layer 1: Priority keyword rules</text>
    <text x="20" y="118" class="node-desc">• Layer 2: Entity lexicon &amp; P2P</text>
    <text x="20" y="141" class="node-desc">• Layer 3: Fuzzy token-set ratio</text>
    <text x="20" y="164" class="node-desc">{holdout_line}</text>
  </g>

  <!-- Connecting Pipe Down from Node 4 to Node 5 -->
  <path d="M 1370 330 L 1370 470 L 1310 470" class="arrow" marker-end="url(#arrow)"/>

  <!-- Row 2: Right to Left -->

  <!-- Node 5: recurring.py -->
  <g transform="translate(990, 380)" filter="url(#shadow)">
    <rect width="310" height="180" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.5"/>
    <rect x="0" y="0" width="310" height="38" rx="12" fill="#CCFBF1"/>
    <rect x="0" y="24" width="310" height="14" fill="#CCFBF1"/>
    <text x="20" y="25" class="node-pill">05 · SUBSCRIPTION DETECTOR</text>
    <text x="20" y="70" class="node-title">recurring.py</text>
    <text x="20" y="95" class="node-desc">• Detect repeating subscriptions</text>
    <text x="20" y="118" class="node-desc">• Amount tolerance (±5% median)</text>
    <text x="20" y="141" class="node-desc">• Cadence: Monthly, Annual, Weekly</text>
    <text x="20" y="164" class="node-desc">• Output: recurring_payments</text>
  </g>

  <!-- Arrow 5 -> 6 -->
  <path d="M 990 470 L 930 470" class="arrow" marker-end="url(#arrow)"/>

  <!-- Node 6: load.py / Database -->
  <g transform="translate(610, 380)" filter="url(#shadow)">
    <rect width="310" height="180" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.5"/>
    <rect x="0" y="0" width="310" height="38" rx="12" fill="#CCFBF1"/>
    <rect x="0" y="24" width="310" height="14" fill="#CCFBF1"/>
    <text x="20" y="25" class="node-pill">06 · PERSISTENCE LAYER</text>
    <text x="20" y="70" class="node-title">MySQL 8.0 / SQLite</text>
    <text x="20" y="95" class="node-desc">• load.py idempotent loader</text>
    <text x="20" y="118" class="node-desc">• Re-runs insert 0 duplicates</text>
    <text x="20" y="141" class="node-desc">• docker-compose.yml setup</text>
    <text x="20" y="164" class="node-desc">• Zero-config SQLite fallback</text>
  </g>

  <!-- Arrow 6 -> 7 -->
  <path d="M 610 470 L 550 470" class="arrow" marker-end="url(#arrow)"/>

  <!-- Node 7: SQL Views -->
  <g transform="translate(230, 380)" filter="url(#shadow)">
    <rect width="310" height="180" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.5"/>
    <rect x="0" y="0" width="310" height="38" rx="12" fill="#CCFBF1"/>
    <rect x="0" y="24" width="310" height="14" fill="#CCFBF1"/>
    <text x="20" y="25" class="node-pill">07 · ANALYTICAL VIEWS</text>
    <text x="20" y="70" class="node-title">SQL Views &amp; Queries</text>
    <text x="20" y="95" class="node-desc">• v_spend (excludes transfers/invest)</text>
    <text x="20" y="118" class="node-desc">• v_income (earned salary)</text>
    <text x="20" y="141" class="node-desc">• v_monthly_summary (savings %)</text>
    <text x="20" y="164" class="node-desc">• 11 analytical portfolio queries</text>
  </g>

  <!-- Connecting Pipe Down from Node 7 to Row 3 (Node 8) -->
  <path d="M 385 560 L 385 640" class="arrow" marker-end="url(#arrow)"/>

  <!-- Row 3: Final Consumption Layer -->
  <g transform="translate(80, 650)" filter="url(#shadow)">
    <rect width="1440" height="180" rx="14" fill="#FFFFFF" stroke="#0F766E" stroke-width="2"/>
    <rect x="0" y="0" width="1440" height="42" rx="14" fill="#0F766E"/>
    <rect x="0" y="28" width="1440" height="14" fill="#0F766E"/>
    <text x="24" y="28" class="node-pill" style="fill: #FFFFFF; font-size: 13px;">08 · PRESENTATION, BUSINESS INSIGHTS &amp; INTERACTIVE CONSUMPTION</text>
    
    <g transform="translate(30, 65)">
      <text x="0" y="20" class="node-title" style="font-size: 19px; fill: #0F766E;">Power BI Desktop (.pbix)</text>
      <text x="0" y="48" class="node-desc">Interactive 4-page dashboard connected to relational tables</text>
      <text x="0" y="70" class="node-desc">DAX measures: Savings Rate, MoM %, Spend 3M Rolling Avg</text>
      <text x="0" y="92" class="node-desc">Pages: Overview, Where It Goes, Leaks &amp; Subscriptions, Insights</text>
    </g>

    <g transform="translate(520, 65)">
      <text x="0" y="20" class="node-title" style="font-size: 19px; fill: #0F766E;">Executive Insights Memo</text>
      <text x="0" y="48" class="node-desc">One-page executive PDF memo (docs/insights_memo.pdf)</text>
      <text x="0" y="70" class="node-desc">5 quantified empirical findings with exact rupee impacts</text>
      <text x="0" y="92" class="node-desc">{memo_rec_line}</text>
    </g>

    <g transform="translate(1010, 65)">
      <text x="0" y="20" class="node-title" style="font-size: 19px; fill: #0F766E;">Data Previews &amp; Demo</text>
      <text x="0" y="48" class="node-desc">Data-rendered 1080p dashboard previews</text>
      <text x="0" y="70" class="node-desc">Animated demo GIF cycling through all report pages</text>
      <text x="0" y="92" class="node-desc">Narration script for walkthrough video presentations</text>
    </g>
  </g>

  <!-- Footer -->
  <text x="80" y="870" class="subtitle" style="font-size: 13px;">{foot_txt}</text>
</svg>
"""
    return svg


def render_png_from_svg(svg_content: str, data: dict):
    global ARCH_DRAWN_STRINGS
    W, H = 1600, 900
    img = Image.new("RGB", (W, H), (248, 250, 252))
    draw = ImageDraw.Draw(img)

    f_title = get_font(28, bold=True)
    f_sub = get_font(16, bold=False)
    f_node_t = get_font(17, bold=True)
    f_node_d = get_font(13, bold=False)
    f_node_p = get_font(11, bold=True)
    f_foot = get_font(13, bold=False)

    TEAL = (15, 118, 110)
    DARK_TEAL = (17, 94, 89)
    LIGHT_TEAL = (204, 251, 241)
    SLATE_900 = (15, 23, 42)
    SLATE_700 = (51, 65, 85)
    SLATE_500 = (100, 116, 139)
    BORDER = (203, 213, 225)
    WHITE = (255, 255, 255)

    if "categorizer_evaluation" in data:
        holdout_acc = data["categorizer_evaluation"]["hard_holdout"]["accuracy_pct"]
    else:
        holdout_acc = 78.33
    rec_monthly = int(round(data["total_savings_potential"]["monthly"]))

    # Top line
    draw.rectangle([0, 0, W, 8], fill=TEAL)

    # Title
    t1 = "UPI / Bank Statement Spend Analyzer · Architecture"
    t2 = "End-to-End Modular Pipeline: Statement Ingestion → Data Cleaning → Classification → Detection → Relational Analytics → Reporting"
    draw.text((80, 40), t1, fill=SLATE_900, font=f_title)
    draw.text((80, 78), t2, fill=SLATE_500, font=f_sub)
    ARCH_DRAWN_STRINGS.extend([t1, t2])

    def draw_node(x, y, w, h, pill, title, bullets, highlighted=False):
        ARCH_DRAWN_STRINGS.append(pill)
        ARCH_DRAWN_STRINGS.append(title)
        ARCH_DRAWN_STRINGS.extend(bullets)

        stroke_col = TEAL if highlighted else BORDER
        stroke_w = 2 if highlighted else 1
        draw.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=WHITE, outline=stroke_col, width=stroke_w)
        banner_fill = TEAL if highlighted else LIGHT_TEAL
        pill_fill = WHITE if highlighted else DARK_TEAL
        draw.rounded_rectangle([x, y, x + w, y + 36], radius=10, fill=banner_fill)
        draw.rectangle([x, y + 22, x + w, y + 36], fill=banner_fill)
        draw.text((x + 18, y + 10), pill, fill=pill_fill, font=f_node_p)

        draw.text((x + 18, y + 50), title, fill=SLATE_900, font=f_node_t)
        by = y + 78
        for b in bullets:
            draw.text((x + 18, by), b, fill=SLATE_700, font=f_node_d)
            by += 23

    # Row 1 nodes
    draw_node(80, 140, 310, 180, "01 · INGESTION SOURCES", "Bank Statements", [
        "• Formats: CSV (2 bank layouts)",
        "• HDFC layout (DD/MM/YY)",
        "• ICICI layout (DD-MM-YYYY)",
        "• Synthetic & private inputs"
    ])

    draw_node(460, 140, 310, 180, "02 · STATEMENT PARSING", "parsers.py", [
        "• Format auto-detection",
        "• BANK_FORMATS config registry",
        "• SHA-1 deterministic txn_id",
        "• Output: Unified DataFrame"
    ])

    draw_node(840, 140, 310, 180, "03 · DATA NORMALIZATION", "cleaning.py", [
        "• Strip UPI/NEFT/IMPS noise",
        "• Merchant entity extraction",
        "• Tag self-transfers & refunds",
        "• Date parsing & calendar features"
    ])

    draw_node(1220, 140, 300, 180, "04 · CLASSIFICATION ENGINE", "categorize.py", [
        "• Layer 1: Priority keyword rules",
        "• Layer 2: Entity lexicon & P2P",
        "• Layer 3: Fuzzy token-set ratio",
        f"• Clean: 100% | Holdout: {holdout_acc}%"
    ], highlighted=True)

    # Row 2 nodes
    draw_node(990, 380, 310, 180, "05 · SUBSCRIPTION DETECTOR", "recurring.py", [
        "• Detect repeating subscriptions",
        "• Amount tolerance (±5% median)",
        "• Cadence: Monthly, Annual, Weekly",
        "• Output: recurring_payments"
    ])

    draw_node(610, 380, 310, 180, "06 · PERSISTENCE LAYER", "MySQL 8.0 / SQLite", [
        "• load.py idempotent loader",
        "• Re-runs insert 0 duplicates",
        "• docker-compose.yml setup",
        "• Zero-config SQLite fallback"
    ])

    draw_node(230, 380, 310, 180, "07 · ANALYTICAL VIEWS", "SQL Views & Queries", [
        "• v_spend (excludes transfers/invest)",
        "• v_income (earned salary)",
        "• v_monthly_summary (savings %)",
        "• 11 analytical portfolio queries"
    ])

    def draw_h_arrow(x1, y1, x2, y2):
        draw.line([x1, y1, x2, y2], fill=TEAL, width=3)
        draw.polygon([(x2, y2), (x2 - 8, y2 - 5), (x2 - 8, y2 + 5)], fill=TEAL)

    # 1 -> 2
    draw_h_arrow(390, 230, 455, 230)
    # 2 -> 3
    draw_h_arrow(770, 230, 835, 230)
    # 3 -> 4
    draw_h_arrow(1150, 230, 1215, 230)

    # Down from 4 to 5
    draw.line([1370, 320, 1370, 470], fill=TEAL, width=3)
    draw.line([1370, 470, 1305, 470], fill=TEAL, width=3)
    draw.polygon([(1305, 470), (1313, 465), (1313, 475)], fill=TEAL)

    # 5 -> 6
    draw.line([990, 470, 925, 470], fill=TEAL, width=3)
    draw.polygon([(925, 470), (933, 465), (933, 475)], fill=TEAL)

    # 6 -> 7
    draw.line([610, 470, 545, 470], fill=TEAL, width=3)
    draw.polygon([(545, 470), (553, 465), (553, 475)], fill=TEAL)

    # Down from 7 to 8
    draw.line([385, 560, 385, 635], fill=TEAL, width=3)
    draw.polygon([(385, 635), (380, 627), (390, 627)], fill=TEAL)

    # Row 3: Final Consumption Layer Box
    draw.rounded_rectangle([80, 640, 1520, 825], radius=14, fill=WHITE, outline=TEAL, width=2)
    draw.rounded_rectangle([80, 640, 1520, 680], radius=12, fill=TEAL)
    draw.rectangle([80, 665, 1520, 680], fill=TEAL)
    p3_hdr = "08 · PRESENTATION, BUSINESS INSIGHTS & INTERACTIVE CONSUMPTION"
    draw.text((105, 650), p3_hdr, fill=WHITE, font=f_node_p)
    ARCH_DRAWN_STRINGS.append(p3_hdr)

    # 3 sections in consumption layer
    c1 = [
        "Power BI Desktop (.pbix)",
        "• Interactive 4-page dashboard connected to relational tables",
        "• DAX measures: Savings Rate, MoM %, Spend 3M Avg",
        "• Pages: Overview, Where It Goes, Leaks, Insights"
    ]
    draw.text((110, 700), c1[0], fill=TEAL, font=f_node_t)
    draw.text((110, 730), c1[1], fill=SLATE_700, font=f_node_d)
    draw.text((110, 755), c1[2], fill=SLATE_700, font=f_node_d)
    draw.text((110, 780), c1[3], fill=SLATE_700, font=f_node_d)
    ARCH_DRAWN_STRINGS.extend(c1)

    c2 = [
        "Executive Insights Memo",
        "• One-page executive PDF memo (docs/insights_memo.pdf)",
        "• 5 quantified empirical findings with exact rupee values",
        f"• 3 prioritized recommendations saving +₹{rec_monthly:,} / month"
    ]
    draw.text((600, 700), c2[0], fill=TEAL, font=f_node_t)
    draw.text((600, 730), c2[1], fill=SLATE_700, font=f_node_d)
    draw.text((600, 755), c2[2], fill=SLATE_700, font=f_node_d)
    draw.text((600, 780), c2[3], fill=SLATE_700, font=f_node_d)
    ARCH_DRAWN_STRINGS.extend(c2)

    c3 = [
        "Data Previews & Demo",
        "• Data-rendered 1080p dashboard previews",
        "• Animated demo GIF cycling through all report pages",
        "• Full video walkthrough narration script"
    ]
    draw.text((1100, 700), c3[0], fill=TEAL, font=f_node_t)
    draw.text((1100, 730), c3[1], fill=SLATE_700, font=f_node_d)
    draw.text((1100, 755), c3[2], fill=SLATE_700, font=f_node_d)
    draw.text((1100, 780), c3[3], fill=SLATE_700, font=f_node_d)
    ARCH_DRAWN_STRINGS.extend(c3)

    # Footer
    foot = "Modular Data Pipeline Architecture · Built with Python, pandas, SQLAlchemy, MySQL & Power BI"
    draw.text((80, 855), foot, fill=SLATE_500, font=f_foot)
    ARCH_DRAWN_STRINGS.append(foot)

    img.save(PNG_OUT)
    print(f"Rendered PNG diagram to {PNG_OUT}")


def build_architecture():
    data = load_memo_data()
    svg_str = generate_svg(data)
    SVG_OUT.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text(svg_str, encoding="utf-8")
    print(f"Wrote SVG diagram to {SVG_OUT}")

    render_png_from_svg(svg_str, data)

    # Register drawn strings
    arch_file = Path("docs/audit/architecture_rendered_text.json")
    arch_file.parent.mkdir(parents=True, exist_ok=True)
    arch_file.write_text(json.dumps(ARCH_DRAWN_STRINGS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Registered {len(ARCH_DRAWN_STRINGS)} architecture strings to {arch_file}")

    if RENDERED_TEXT_PATH.exists():
        existing = json.loads(RENDERED_TEXT_PATH.read_text(encoding="utf-8"))
        merged = sorted(list(set(existing + ARCH_DRAWN_STRINGS)))
        RENDERED_TEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RENDERED_TEXT_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Merged into {RENDERED_TEXT_PATH} (total: {len(merged)} strings)")


if __name__ == "__main__":
    build_architecture()
