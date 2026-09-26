"""Rebuild static/img/share.jpg, the 1200x630 picture shown when the site's
link is shared on Facebook, LINE, X, etc.

It uses the headline and sub-headline from data/site.json, the logo and a
few site photos, so run it again whenever you change the headline:

    pip install pillow            # once
    python scripts/make_share_image.py
"""

import json
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    raise SystemExit("Pillow is needed: run  pip install pillow  and try again.")

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "static" / "img"

W, H = 1200, 630
TEXT_MAX_W = 520
BG = (253, 241, 242)
ROSE = (176, 71, 90)
INK = (77, 77, 79)
MUTED = (109, 110, 113)
WHITE = (255, 255, 255)

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
REGULAR = FONT_DIR / "DejaVuSans.ttf"

# (photo, x, y, width, height) for the mosaic on the right-hand side
MOSAIC = [
    ("volunteer/farm-garden.jpg", 600, 40, 270, 550),
    ("volunteer/teaching.jpg", 884, 40, 276, 180),
    ("horses/horse2.jpg", 884, 234, 131, 172),
    ("horses/horse4.jpg", 1029, 234, 131, 172),
    ("volunteer/kayaking.jpg", 884, 420, 276, 170),
]


def font(path, size):
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:  # DejaVu not installed: fall back to Pillow's own font
        return ImageFont.load_default(size)


def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *im.size), radius, fill=255)
    out = Image.new("RGBA", im.size)
    out.paste(im, (0, 0), mask)
    return out


def wrap(draw, text, fnt, max_w):
    """Split text into lines that fit max_w pixels."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def hex_rgb(value, default):
    """'#b0475a' -> (176, 71, 90); anything else -> default."""
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    return default


def main():
    site = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
    colors = site.get("text_colors") or {}  # same colours as the home page
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    for path, x, y, w, h in MOSAIC:
        photo = ImageOps.fit(Image.open(IMG / path).convert("RGB"), (w, h), Image.LANCZOS)
        tile = rounded(photo, 18)
        img.paste(tile, (x, y), tile)

    logo = Image.open(IMG / "logo.png").convert("RGB")
    logo.thumbnail((210, 190), Image.LANCZOS)
    card = Image.new("RGB", (logo.width + 24, logo.height + 24), WHITE)
    card.paste(logo, (12, 12))
    card = rounded(card, 20)
    img.paste(card, (48, 40), card)
    y = 40 + card.height + 28

    # Headline: as large as fits on one line (max 58px)
    headline = site["headline"]
    size = 58
    while draw.textlength(headline, font=font(BOLD, size)) > TEXT_MAX_W and size > 30:
        size -= 1
    head_font = font(BOLD, size)
    draw.text((48, y), headline, font=head_font, fill=hex_rgb(colors.get("headline"), INK))
    y += int(size * 1.3)

    sub = site.get("headline_sub", "")
    if sub:
        # One line if it fits at 22px or more, otherwise wrap
        sub_size = 30
        while draw.textlength(sub, font=font(BOLD, sub_size)) > TEXT_MAX_W and sub_size > 22:
            sub_size -= 1
        sub_font = font(BOLD, sub_size)
        for line in wrap(draw, sub, sub_font, TEXT_MAX_W):
            draw.text((50, y), line, font=sub_font, fill=hex_rgb(colors.get("headline_sub"), ROSE))
            y += int(sub_size * 1.35)
        y += 12

    body_font = font(REGULAR, 22)
    for line in wrap(draw, site["tagline"], body_font, TEXT_MAX_W):
        draw.text((50, y), line, font=body_font, fill=MUTED)
        y += 31

    pill_font = font(BOLD, 21)
    label = "Donate  ·  Volunteer  ·  Visit"
    y = max(y + 16, H - 40 - 46)  # sit on the bottom edge, level with the photos
    tw = draw.textlength(label, font=pill_font)
    draw.rounded_rectangle((48, y, 48 + tw + 44, y + 46), 23, fill=ROSE)
    draw.text((70, y + 11), label, font=pill_font, fill=WHITE)
    if y + 46 > H - 20:
        print("Warning: text is too long and may be cut off; shorten the tagline.")

    out = IMG / "share.jpg"
    img.save(out, quality=88, optimize=True)
    print(f"Saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
