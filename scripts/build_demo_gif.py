# scripts/build_demo_gif.py
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SCREENSHOTS_DIR = Path("powerbi/screenshots")
GIF_OUT = Path("docs/demo.gif")
MEMO_PATH = Path("docs/memo_numbers.json")

TARGET_W = 1280
TARGET_H = 720


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


GIF_SOURCE_STRINGS = []


def create_title_frame() -> Image.Image:
    global GIF_SOURCE_STRINGS
    memo = json.loads(MEMO_PATH.read_text(encoding="utf-8"))
    ctx = memo["context"]
    f1 = memo["findings"]["f1_subscriptions"]
    tot = memo["total_savings_potential"]

    img = Image.new("RGB", (TARGET_W, TARGET_H), (15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(img)

    f_title = get_font(44, bold=True)
    f_sub = get_font(24, bold=False)
    f_pill = get_font(16, bold=True)
    f_meta = get_font(16, bold=False)

    TEAL = (15, 118, 110)
    LIGHT_TEAL = (204, 251, 241)
    WHITE = (255, 255, 255)
    SLATE_400 = (148, 163, 184)

    # Top accent bar
    draw.rectangle([0, 0, TARGET_W, 10], fill=TEAL)

    def text_bbox_w(text_str: str, font) -> int:
        bbox = font.getbbox(text_str)
        return bbox[2] - bbox[0]

    # Center badge
    badge_str = "PORTFOLIO DEMO · 12-MONTH REVIEW"
    GIF_SOURCE_STRINGS.append(badge_str)
    badge_text_w = text_bbox_w(badge_str, f_pill)
    pad_x = 24
    badge_w = badge_text_w + 2 * pad_x
    badge_x0 = (TARGET_W - badge_w) // 2
    draw.rounded_rectangle([badge_x0, 160, badge_x0 + badge_w, 204], radius=20, fill=TEAL)
    draw.text((badge_x0 + pad_x, 172), badge_str, fill=LIGHT_TEAL, font=f_pill)

    # Title
    t1 = "UPI / Bank Statement Spend Analyzer"
    t2 = "Automated Pipeline, Relational Schema & Power BI Dashboard"
    GIF_SOURCE_STRINGS.extend([t1, t2])
    t1_w = text_bbox_w(t1, f_title)
    t2_w = text_bbox_w(t2, f_sub)
    draw.text(((TARGET_W - t1_w) // 2, 240), t1, fill=WHITE, font=f_title)
    draw.text(((TARGET_W - t2_w) // 2, 310), t2, fill=SLATE_400, font=f_sub)

    # 4 Quick Metric Highlights (Dynamically from memo_numbers.json)
    kpi_y = 410
    kpis = [
        ("TOTAL SPEND", format_inr(ctx["total_spend"])),
        ("SAVINGS RATE", f"{ctx['savings_rate_pct']}%"),
        ("SUBSCRIPTIONS", f"{format_inr(f1['annual_cost'])}/yr"),
        ("SCENARIO SAVING", f"+{format_inr(round(tot['monthly']))}/mo"),
    ]
    box_w = 230
    box_gap = 24
    start_x = (TARGET_W - (4 * box_w + 3 * box_gap)) // 2

    for i, (k_lbl, k_val) in enumerate(kpis):
        GIF_SOURCE_STRINGS.extend([k_lbl, k_val])
        bx = start_x + i * (box_w + box_gap)
        draw.rounded_rectangle([bx, kpi_y, bx + box_w, kpi_y + 110], radius=10, fill=(30, 41, 59), outline=(51, 65, 85), width=1)
        draw.text((bx + 20, kpi_y + 18), k_lbl, fill=SLATE_400, font=f_meta)
        draw.text((bx + 20, kpi_y + 48), k_val, fill=LIGHT_TEAL if i == 3 else WHITE, font=get_font(26, bold=True))

    # Bottom footer line
    f_str = "Python · pandas · MySQL 8.0 · SQL Views · Power BI Desktop"
    GIF_SOURCE_STRINGS.append(f_str)
    foot_w = text_bbox_w(f_str, f_meta)
    draw.text(((TARGET_W - foot_w) // 2, 620), f_str, fill=SLATE_400, font=f_meta)

    return img


def build_gif():
    # Load 4 screenshots
    pages = [
        "01_overview.png",
        "02_where_it_goes.png",
        "03_leaks_subscriptions.png",
        "04_insights.png",
    ]

    loaded_imgs = []
    # 1. Add title frame
    title_img = create_title_frame()
    loaded_imgs.append(title_img)

    for p in pages:
        p_path = SCREENSHOTS_DIR / p
        img = Image.open(p_path).convert("RGB")
        resized = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
        loaded_imgs.append(resized)

    # Export first frame and one frame per page to docs/gif_check/ (uncommitted/gitignored)
    check_dir = Path("docs/gif_check")
    check_dir.mkdir(parents=True, exist_ok=True)
    title_img.save(check_dir / "frame_00_title.png")
    for idx, p in enumerate(pages, 1):
        loaded_imgs[idx].save(check_dir / f"frame_{idx:02d}_{p}")
    print(f"Exported title frame and page frames to {check_dir}")

    # Build sequence with smooth transitions
    # Each main page held for 3000ms (~3s), transitions have 4 frames of 100ms
    frames = []
    durations = []

    # Title frame: hold 2500ms
    frames.append(loaded_imgs[0])
    durations.append(2500)

    # Loop through pages with transitions
    for i in range(1, len(loaded_imgs)):
        curr_img = loaded_imgs[i]
        prev_img = loaded_imgs[i - 1]

        # 3 fade frames between prev and curr
        for alpha in [0.3, 0.6, 0.9]:
            blended = Image.blend(prev_img, curr_img, alpha)
            frames.append(blended)
            durations.append(100)

        # Hold main page for 3200ms
        frames.append(curr_img)
        durations.append(3200)

    # Loop back transition from last page to title frame
    for alpha in [0.3, 0.6, 0.9]:
        blended = Image.blend(loaded_imgs[-1], loaded_imgs[0], alpha)
        frames.append(blended)
        durations.append(100)

    # Save animated GIF
    GIF_OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        GIF_OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    file_size_mb = GIF_OUT.stat().st_size / (1024 * 1024)
    print(f"Generated {GIF_OUT} ({len(frames)} frames, {file_size_mb:.2f} MB)")


if __name__ == "__main__":
    build_gif()
