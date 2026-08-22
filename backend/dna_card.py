"""Generate a shareable Creator DNA card as PNG (1200x675, Twitter-sized)."""
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 1200, 675
BG = (10, 10, 15)
SURFACE = (18, 18, 26)
ACCENT = (138, 43, 226)
TEXT = (248, 249, 250)
MUTED = (161, 161, 170)

# Try common bundled fonts; fall back to PIL default
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size: int, bold: bool = False):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            if bold and "Bold" in p:
                return ImageFont.truetype(p, size)
            if not bold and "Bold" not in p:
                return ImageFont.truetype(p, size)
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _rounded(draw, xy, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def render_dna_card(creator: dict) -> bytes:
    img = Image.new("RGB", (W, H), BG)

    # Gradient glow top-left
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(400, 0, -20):
        alpha = int(60 * (1 - r / 400))
        gd.ellipse((-200 - r, -200 - r, 400 + r, 400 + r), fill=(138, 43, 226, alpha))
    img.paste(glow, (0, 0), glow)

    draw = ImageDraw.Draw(img)

    # Brand row
    draw.ellipse((60, 60, 90, 90), fill=ACCENT)
    draw.text((100, 62), "CreatorOS", font=_font(24, bold=True), fill=TEXT)
    draw.text((100, 90), "creator DNA", font=_font(14), fill=MUTED)

    # Avatar circle
    ax, ay, ar = 80, 200, 60
    draw.ellipse((ax - ar, ay - ar, ax + ar, ay + ar), fill=ACCENT)
    initials = creator.get("initials", "?")
    tw = draw.textlength(initials, font=_font(44, bold=True))
    draw.text((ax - tw / 2, ay - 30), initials, font=_font(44, bold=True), fill=TEXT)

    # Name
    draw.text((170, 175), creator.get("name", ""), font=_font(48, bold=True), fill=TEXT)
    subs_txt = f"{creator.get('subscribers', 0) // 1000}K subs · {creator.get('niche', '')}"
    draw.text((170, 235), subs_txt, font=_font(22), fill=MUTED)

    # Pillars section
    y0 = 320
    draw.text((60, y0 - 40), "CONTENT PILLARS", font=_font(14, bold=True), fill=(196, 181, 253))
    for i, p in enumerate(creator.get("pillars", [])[:5]):
        row_y = y0 + i * 52
        draw.text((60, row_y), p["name"], font=_font(20, bold=True), fill=TEXT)
        draw.text((60, row_y + 24), f"{p['pct']}%", font=_font(14), fill=MUTED)
        # Bar
        bar_x, bar_w = 320, 320
        _rounded(draw, (bar_x, row_y + 16, bar_x + bar_w, row_y + 24), radius=4, fill=(255, 255, 255, 20))
        fill_w = int(bar_w * (p["pct"] / 40))
        _rounded(draw, (bar_x, row_y + 16, bar_x + fill_w, row_y + 24), radius=4, fill=ACCENT)

    # Right column — best format
    rx = 720
    _rounded(draw, (rx, 320, W - 60, H - 100), radius=24, outline=(255, 255, 255, 30), width=1)
    draw.text((rx + 28, 340), "BEST FORMAT", font=_font(14, bold=True), fill=(196, 181, 253))
    fmt = (creator.get("formats") or [{}])[0]
    draw.text((rx + 28, 370), fmt.get("name", ""), font=_font(38, bold=True), fill=TEXT)
    draw.text((rx + 28, 420), f"{fmt.get('multiplier', 1)}× baseline", font=_font(20), fill=(16, 185, 129))

    # Style
    style = creator.get("style", {}) or {}
    draw.text((rx + 28, 480), "VOICE", font=_font(14, bold=True), fill=(196, 181, 253))
    draw.text((rx + 28, 508), (style.get("tone") or "")[:38], font=_font(18), fill=TEXT)
    draw.text((rx + 28, 536), (style.get("hook_style") or "")[:38], font=_font(16), fill=MUTED)

    # Footer
    draw.line((60, H - 70, W - 60, H - 70), fill=(255, 255, 255, 20), width=1)
    draw.text((60, H - 50), "creatoros.app", font=_font(16, bold=True), fill=TEXT)
    draw.text((W - 320, H - 50), "know what to create next.", font=_font(16), fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
