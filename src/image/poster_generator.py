"""
Generates 1080x1080 Instagram-ready collage images using official TMDb poster artwork.

Daily layout (up to 6 posters in a 3-column grid):

  ┌──────────────────────────────────────────────────┐  ← 4px accent stripe
  │  🎬 OTT RELEASES TODAY          June 07, 2025    │  header (100px)
  ├──────────────────────────────────────────────────┤
  │ [poster+badge] [poster+badge] [poster+badge]      │  row 1
  │   title          title          title             │
  ├──────────────────────────────────────────────────┤
  │ [poster+badge] [poster+badge] [poster+badge]      │  row 2
  │   title          title          title             │
  ├──────────────────────────────────────────────────┤
  │  where2watch  •  #OTTReleases #StreamingNow       │  footer (56px)
  └──────────────────────────────────────────────────┘  ← 4px accent stripe
"""
from __future__ import annotations

import io
import logging
import textwrap
from datetime import date
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from src.aggregator.models import Release
from src.aggregator.platforms import Platform, get_platform_by_id, load_platforms
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
_BG = (12, 12, 18)
_CARD = (24, 24, 32)
_TEXT = (245, 245, 250)
_MUTED = (140, 140, 160)
_ACCENT = (229, 9, 20)

# ── Layout constants ──────────────────────────────────────────────────────────
_HEADER_H = 100
_FOOTER_H = 56
_PAD = 12
_COLS = 3
_BADGE_H = 26
_TITLE_H = 30
_CORNER_R = 6


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    logger.debug("No TrueType font found, using default bitmap font")
    return ImageFont.load_default()


def _download_poster(url: str) -> Optional[Image.Image]:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        return img.convert("RGB")
    except Exception as exc:
        logger.warning("Poster download failed (%s): %s", url, exc)
        return None


def _placeholder(width: int, height: int, title: str, bg_color: str) -> Image.Image:
    img = Image.new("RGB", (width, height), _hex_to_rgb(bg_color))
    draw = ImageDraw.Draw(img)
    font = _load_font(14, bold=True)
    lines = textwrap.wrap(title, width=13)[:4]
    total_h = len(lines) * 18
    y = (height - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, fill=_TEXT, font=font)
        y += 18
    return img


def _draw_gradient(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    top = (18, 18, 28)
    bot = (8, 8, 14)
    for y in range(canvas.height):
        r = int(top[0] + (bot[0] - top[0]) * y / canvas.height)
        g = int(top[1] + (bot[1] - top[1]) * y / canvas.height)
        b = int(top[2] + (bot[2] - top[2]) * y / canvas.height)
        draw.line([(0, y), (canvas.width, y)], fill=(r, g, b))


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    y: int,
    canvas_width: int,
    color: tuple[int, int, int],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (canvas_width - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, fill=color, font=font)


def _add_badge(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    platform: Platform,
    cell_x: int,
    cell_y: int,
    cell_w: int,
    poster_h: int,
) -> None:
    font = _load_font(11, bold=True)
    label = platform.display_name
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    px, py = 6, 3
    bw = tw + px * 2
    bh = _BADGE_H - 4
    bx = cell_x + (cell_w - bw) // 2
    by = cell_y + poster_h - bh - 4
    bg = _hex_to_rgb(platform.color)
    fg = _hex_to_rgb(platform.text_color)
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=3, fill=bg)
    draw.text((bx + px, by + py), label, fill=fg, font=font)


class PosterGenerator:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.platforms = load_platforms()

    def generate_daily(
        self,
        releases: list[Release],
        target_date: Optional[date] = None,
    ) -> Image.Image:
        if target_date is None:
            target_date = date.today()

        W, H = self.settings.image_width, self.settings.image_height
        canvas = Image.new("RGB", (W, H))
        _draw_gradient(canvas)
        draw = ImageDraw.Draw(canvas)

        # ── Accent stripe top ─────────────────────────────────────────────────
        draw.rectangle([0, 0, W, 4], fill=_ACCENT)

        # ── Header ────────────────────────────────────────────────────────────
        title_font = _load_font(32, bold=True)
        date_font = _load_font(16)

        title_text = "\U0001f3ac  OTT RELEASES TODAY"
        date_text = target_date.strftime("%B %d, %Y").upper()

        _draw_centered_text(draw, title_text, title_font, 14, W, _TEXT)
        _draw_centered_text(draw, date_text, date_font, 58, W, _MUTED)
        draw.line([(_PAD * 2, _HEADER_H - 1), (W - _PAD * 2, _HEADER_H - 1)], fill=(40, 40, 55))

        # ── Poster grid ───────────────────────────────────────────────────────
        display = releases[:6]
        rows = max(1, min(2, (len(display) + _COLS - 1) // _COLS))

        content_h = H - _HEADER_H - _FOOTER_H
        cell_w = (W - _PAD * (_COLS + 1)) // _COLS
        cell_h = (content_h - _PAD * (rows + 1)) // rows
        poster_h = cell_h - _TITLE_H

        for idx, release in enumerate(display):
            row, col = divmod(idx, _COLS)
            cx = _PAD + col * (cell_w + _PAD)
            cy = _HEADER_H + _PAD + row * (cell_h + _PAD)

            draw.rounded_rectangle([cx, cy, cx + cell_w, cy + cell_h], radius=_CORNER_R, fill=_CARD)

            platform = get_platform_by_id(release.platform, self.platforms)
            fallback_color = platform.color if platform else "#333344"

            poster_img: Optional[Image.Image]
            if release.poster_url:
                poster_img = _download_poster(release.poster_url)
            else:
                poster_img = None

            if poster_img:
                cropped = ImageOps.fit(poster_img, (cell_w, poster_h), method=Image.LANCZOS)
            else:
                cropped = _placeholder(cell_w, poster_h, release.title, fallback_color)

            # Rounded-corner mask for poster
            mask = Image.new("L", (cell_w, poster_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, cell_w, poster_h], radius=_CORNER_R, fill=255)
            canvas.paste(cropped, (cx, cy), mask)

            if platform:
                _add_badge(canvas, draw, platform, cx, cy, cell_w, poster_h)

            # Title text below poster image
            title_font_sm = _load_font(12)
            short_title = release.title[:22] + "…" if len(release.title) > 22 else release.title
            tbbox = draw.textbbox((0, 0), short_title, font=title_font_sm)
            tx = cx + (cell_w - (tbbox[2] - tbbox[0])) // 2
            draw.text((tx, cy + poster_h + 4), short_title, fill=_TEXT, font=title_font_sm)

        # ── Footer ────────────────────────────────────────────────────────────
        fy = H - _FOOTER_H
        draw.line([(_PAD * 2, fy), (W - _PAD * 2, fy)], fill=(40, 40, 55))
        footer_font = _load_font(14)
        _draw_centered_text(
            draw,
            "where2watch  •  #OTTReleases  #StreamingNow",
            footer_font,
            fy + 16,
            W,
            _MUTED,
        )
        draw.rectangle([0, H - 4, W, H], fill=_ACCENT)

        return canvas

    def generate_weekly_slides(
        self,
        releases_by_platform: dict[str, list[Release]],
        week_label: str,
    ) -> list[Image.Image]:
        """Returns one slide per platform (for a carousel post)."""
        slides: list[Image.Image] = []
        for platform_id, releases in releases_by_platform.items():
            platform = get_platform_by_id(platform_id, self.platforms)
            if platform:
                slides.append(self._platform_slide(platform, releases, week_label))
        return slides

    def _platform_slide(
        self, platform: Platform, releases: list[Release], week_label: str
    ) -> Image.Image:
        W, H = self.settings.image_width, self.settings.image_height
        bg = _hex_to_rgb(platform.color)
        canvas = Image.new("RGB", (W, H), bg)

        # Dark overlay
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 160))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        # Platform name
        h1 = _load_font(44, bold=True)
        h2 = _load_font(18)
        item_f = _load_font(20)

        _draw_centered_text(draw, platform.display_name.upper(), h1, 60, W, _TEXT)
        _draw_centered_text(draw, f"Weekly Watchlist  •  {week_label}", h2, 120, W, _MUTED)
        draw.line([(60, 162), (W - 60, 162)], fill=(255, 255, 255, 60))

        y = 188
        for i, r in enumerate(releases[:8], 1):
            label = f"{i}. {r.title}"
            if r.rating:
                label += f"  ★ {r.rating:.1f}"
            draw.text((80, y), label, fill=_TEXT, font=item_f)
            y += 38

        footer_f = _load_font(14)
        _draw_centered_text(draw, "#where2watch  #WeeklyWatchlist", footer_f, H - 50, W, _MUTED)
        return canvas
