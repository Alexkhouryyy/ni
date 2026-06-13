"""Generate Apex PWA icons from scratch (no source art needed).

Draws a glowing upward "apex" double-chevron mark in the dashboard's cyan→purple
gradient on a dark radial background. Produces the icon set referenced by
dashboard/static/manifest.webmanifest.

Run: python scripts/gen_pwa_icons.py
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "icons")

BG_CENTER = (17, 22, 31)    # #11161f
BG_EDGE = (7, 11, 20)       # #070b14
CYAN = (102, 204, 255)      # #6cf
PURPLE = (138, 124, 255)    # #8a7cff


def _radial_bg(size: int, full_bleed: bool) -> Image.Image:
    """Dark radial gradient. full_bleed fills the whole square (maskable)."""
    img = Image.new("RGB", (size, size), BG_EDGE)
    px = img.load()
    cx = cy = size / 2
    maxd = math.hypot(cx, cy)
    for y in range(size):
        for x in range(size):
            t = math.hypot(x - cx, y - cy) / maxd
            t = min(1.0, t)
            px[x, y] = (
                int(BG_CENTER[0] * (1 - t) + BG_EDGE[0] * t),
                int(BG_CENTER[1] * (1 - t) + BG_EDGE[1] * t),
                int(BG_CENTER[2] * (1 - t) + BG_EDGE[2] * t),
            )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if full_bleed:
        out.paste(img, (0, 0))
    else:
        # Rounded-rect tile so non-maskable icons read as an app tile.
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255
        )
        out.paste(img, (0, 0), mask)
    return out


def _v_gradient(size: int) -> Image.Image:
    """Vertical cyan(top)→purple(bottom) gradient."""
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(CYAN[0] * (1 - t) + PURPLE[0] * t)
        g = int(CYAN[1] * (1 - t) + PURPLE[1] * t)
        b = int(CYAN[2] * (1 - t) + PURPLE[2] * t)
        for x in range(size):
            px[x, y] = (r, g, b, 255)
    return grad


def _chevron(draw: ImageDraw.ImageDraw, size: int, cx: float, peak_y: float,
             half_w: float, thick: float) -> None:
    """Draw one filled upward chevron (^) centred on cx with apex at peak_y."""
    drop = half_w  # 45° legs
    pts = [
        (cx, peak_y),                          # outer peak
        (cx + half_w, peak_y + drop),          # right outer
        (cx + half_w - thick, peak_y + drop),  # right inner
        (cx, peak_y + thick * 1.5),            # inner peak
        (cx - half_w + thick, peak_y + drop),  # left inner
        (cx - half_w, peak_y + drop),          # left outer
    ]
    draw.polygon(pts, fill=255)


def _glyph_mask(size: int) -> Image.Image:
    """White double-chevron 'apex' mark on black (alpha mask)."""
    ss = size * 4  # supersample for smooth edges
    mask = Image.new("L", (ss, ss), 0)
    d = ImageDraw.Draw(mask)
    cx = ss / 2
    half_w = ss * 0.26
    thick = ss * 0.085
    _chevron(d, ss, cx, ss * 0.26, half_w, thick)            # upper, larger
    _chevron(d, ss, cx, ss * 0.50, half_w * 0.78, thick)     # lower, smaller
    return mask.resize((size, size), Image.LANCZOS)


def make_icon(size: int, maskable: bool) -> Image.Image:
    bg = _radial_bg(size, full_bleed=maskable)
    scale = 0.62 if maskable else 0.78  # maskable keeps glyph in the safe zone
    glyph_size = int(size * scale)
    mask = _glyph_mask(glyph_size)
    grad = _v_gradient(glyph_size)

    glyph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = (size - glyph_size) // 2
    glyph.paste(grad, (off, off), mask)

    # Soft glow underneath.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gmask = Image.new("L", (size, size), 0)
    gmask.paste(mask, (off, off))
    glow_color = Image.new("RGBA", (size, size), CYAN + (255,))
    glow.paste(glow_color, (0, 0), gmask)
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.04))

    out = bg.convert("RGBA")
    out = Image.alpha_composite(out, glow)
    out = Image.alpha_composite(out, glyph)
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    specs = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-192.png", 192, True),
        ("icon-maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, True),
        ("favicon-64.png", 64, False),
    ]
    for name, size, maskable in specs:
        img = make_icon(size, maskable)
        img.save(os.path.join(OUT, name))
        print(f"wrote {name} ({size}x{size}{' maskable' if maskable else ''})")


if __name__ == "__main__":
    main()
