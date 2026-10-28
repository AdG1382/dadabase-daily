"""Draws every image: carousel slides, video frames, website share cards and the mascot."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .queue import Joke

F_BLACK = str(config.FONTS / "Inter-Black.otf")
F_XBOLD = str(config.FONTS / "Inter-ExtraBold.otf")
F_BOLD = str(config.FONTS / "Inter-Bold.otf")
F_SEMI = str(config.FONTS / "Inter-SemiBold.otf")

# Four looks that rotate so the feed doesn't read as one template stamped 300 times.
THEMES = [
    {"name": "chai",  "bg": "#FFF3DF", "panel": "#FFFFFF", "ink": "#3B2314", "muted": "#8A6A55", "accent": "#E8772E", "accent_ink": "#FFFFFF"},
    {"name": "night", "bg": "#15203A", "panel": "#1F2C4D", "ink": "#FFFFFF", "muted": "#AEB8D0", "accent": "#FFC43D", "accent_ink": "#15203A"},
    {"name": "mint",  "bg": "#E3F4EA", "panel": "#FFFFFF", "ink": "#0F3B2A", "muted": "#4F7A66", "accent": "#1E9E6A", "accent_ink": "#FFFFFF"},
    {"name": "pop",   "bg": "#FF6B5B", "panel": "#FFF7F2", "ink": "#2B1A17", "muted": "#7A4E46", "accent": "#2B1A17", "accent_ink": "#FFFFFF"},
]

CATEGORY_LABEL = {
    "food": "Food", "family": "Family", "work": "Office", "school": "School & exams",
    "sports": "Cricket & sports", "tech": "Tech", "travel": "Travel & traffic",
    "weather": "Weather", "festivals": "Festivals", "music": "Music & movies",
    "animals": "Animals", "science": "Science", "puns": "Classic puns",
}


def theme_for(joke: Joke) -> dict:
    return THEMES[joke.index % len(THEMES)]


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, path, max_w, max_h, start, minimum, spacing=1.22):
    size = start
    while size >= minimum:
        font = _font(path, size)
        lines = _wrap(draw, text, font, max_w)
        if len(lines) * size * spacing <= max_h and all(draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines, size
        size -= 4
    font = _font(path, minimum)
    return font, _wrap(draw, text, font, max_w), minimum


def _draw_block(draw, lines, font, size, x, y, fill, spacing=1.22, align="left", width=0):
    for i, line in enumerate(lines):
        lx = x
        if align == "center":
            lx = x + (width - draw.textlength(line, font=font)) / 2
        draw.text((lx, y + i * size * spacing), line, font=font, fill=fill)
    return y + len(lines) * size * spacing


def draw_mascot(size: int, theme: dict | None = None) -> Image.Image:
    """Original cartoon dad: round face, side hair, big glasses, moustache. Drawn from shapes."""
    t = theme or THEMES[0]
    s = size / 100
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2 * s, 2 * s, 98 * s, 98 * s], fill=t["accent"])                    # badge
    d.ellipse([20 * s, 18 * s, 80 * s, 86 * s], fill="#F2C29B")                       # face
    d.pieslice([18 * s, 12 * s, 82 * s, 60 * s], 180, 360, fill="#2E1E14")            # hair
    d.ellipse([26 * s, 22 * s, 74 * s, 44 * s], fill="#F2C29B")                       # forehead (receding hairline)
    d.ellipse([14 * s, 44 * s, 24 * s, 60 * s], fill="#E8B088")                       # ears
    d.ellipse([76 * s, 44 * s, 86 * s, 60 * s], fill="#E8B088")
    for cx in (39, 61):                                                               # glasses
        d.ellipse([(cx - 10) * s, 42 * s, (cx + 10) * s, 60 * s], fill="#FFFFFF", outline="#2E1E14", width=max(2, int(2.6 * s)))
        d.ellipse([(cx - 3) * s, 48 * s, (cx + 3) * s, 54 * s], fill="#2E1E14")
    d.line([49 * s, 50 * s, 51 * s, 50 * s], fill="#2E1E14", width=max(2, int(2.6 * s)))
    d.chord([34 * s, 60 * s, 66 * s, 78 * s], 180, 360, fill="#2E1E14")               # moustache
    d.arc([40 * s, 66 * s, 60 * s, 80 * s], 20, 160, fill="#7A3B22", width=max(2, int(2.2 * s)))  # grin
    return img


def _header(img, draw, t, x, y, scale=1.0):
    m = draw_mascot(int(78 * scale), t)
    img.paste(m, (x, y), m)
    draw.text((x + int(96 * scale), y + int(10 * scale)), config.BRAND.upper(), font=_font(F_BLACK, int(30 * scale)), fill=t["ink"])
    draw.text((x + int(96 * scale), y + int(46 * scale)), "one dad joke a day", font=_font(F_SEMI, int(22 * scale)), fill=t["muted"])


def _chip(draw, text, x, y, t, size=26):
    f = _font(F_BOLD, size)
    w = draw.textlength(text, font=f)
    draw.rounded_rectangle([x, y, x + w + 36, y + size + 24], radius=(size + 24) // 2, fill=t["accent"])
    draw.text((x + 18, y + 10), text, font=f, fill=t["accent_ink"])


def carousel_slides(joke: Joke, out_dir: Path) -> list[Path]:
    """Two 1080x1350 JPEGs: the setup, then the punchline."""
    out_dir.mkdir(parents=True, exist_ok=True)
    t = theme_for(joke)
    W, H, pad = 1080, 1350, 80
    paths = []

    # Slide 1: setup
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    _header(img, d, t, pad, pad, 1.5)
    _chip(d, CATEGORY_LABEL.get(joke.category, joke.category.title()), pad, 260, t, 34)
    font, lines, size = _fit(d, joke.setup, F_XBOLD, W - 2 * pad, 640, 100, 52)
    block_h = len(lines) * size * 1.22
    _draw_block(d, lines, font, size, pad, 370 + (640 - block_h) / 2, t["ink"])
    d.text((pad, H - pad - 40), "Swipe for the punchline  →", font=_font(F_BOLD, 38), fill=t["accent"] if t["name"] != "pop" else t["ink"])
    p1 = out_dir / f"{joke.id}-1.jpg"
    img.save(p1, "JPEG", quality=90)
    paths.append(p1)

    # Slide 2: punchline
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    _header(img, d, t, pad, pad, 1.5)
    sfont, slines, ssize = _fit(d, joke.setup, F_SEMI, W - 2 * pad, 240, 44, 30)
    y = _draw_block(d, slines, sfont, ssize, pad, 270, t["muted"])
    panel_top = y + 40
    d.rounded_rectangle([pad - 20, panel_top, W - pad + 20, H - 230], radius=40, fill=t["panel"])
    pfont, plines, psize = _fit(d, joke.punchline, F_BLACK, W - 2 * pad - 60, (H - 230) - panel_top - 100, 104, 50)
    pblock = len(plines) * psize * 1.22
    ptop = panel_top + ((H - 230) - panel_top - pblock) / 2
    _draw_block(d, plines, pfont, psize, pad + 10, ptop, t["ink"] if t["name"] != "night" else "#FFFFFF",
                align="center", width=W - 2 * pad - 20)
    d.text((pad, H - pad - 80), "Rate this groan 1–10 in the comments", font=_font(F_BOLD, 34), fill=t["ink"])
    d.text((pad, H - pad - 30), f"{config.HANDLE}  ·  new joke every day", font=_font(F_SEMI, 28), fill=t["muted"])
    p2 = out_dir / f"{joke.id}-2.jpg"
    img.save(p2, "JPEG", quality=90)
    paths.append(p2)
    return paths


def video_frames(joke: Joke, out_dir: Path) -> tuple[Path, Path]:
    """Two 1080x1920 frames for the Short: setup alone, then setup + punchline."""
    out_dir.mkdir(parents=True, exist_ok=True)
    t = theme_for(joke)
    W, H, pad = 1080, 1920, 90

    def base():
        img = Image.new("RGB", (W, H), t["bg"])
        d = ImageDraw.Draw(img)
        _header(img, d, t, pad, 300, 1.7)
        _chip(d, CATEGORY_LABEL.get(joke.category, joke.category.title()), pad, 500, t, 36)
        return img, d

    img, d = base()
    font, lines, size = _fit(d, joke.setup, F_XBOLD, W - 2 * pad, 520, 108, 56)
    end = _draw_block(d, lines, font, size, pad, 680, t["ink"])
    d.text((pad, end + 110), "wait for it…", font=_font(F_BOLD, 52), fill=t["muted"])
    f1 = out_dir / f"{joke.id}-v1.png"
    img.save(f1)

    img, d = base()
    y = _draw_block(d, lines, font, size, pad, 680, t["ink"])
    top = y + 60
    pfont, plines, psize = _fit(d, joke.punchline, F_BLACK, W - 2 * pad - 60, 1500 - top - 90, 100, 50)
    pblock = len(plines) * psize * 1.22
    d.rounded_rectangle([pad - 20, top, W - pad + 20, top + pblock + 90], radius=44, fill=t["accent"])
    _draw_block(d, plines, pfont, psize, pad + 10, top + 45, t["accent_ink"])
    d.text((pad, 1560), f"Follow {config.HANDLE} for daily groans", font=_font(F_BOLD, 40), fill=t["ink"])
    f2 = out_dir / f"{joke.id}-v2.png"
    img.save(f2)
    return f1, f2


def share_card(joke: Joke, path: Path) -> Path:
    """1200x630 preview image used when a joke page is shared (setup only, no spoiler)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = theme_for(joke)
    img = Image.new("RGB", (1200, 630), t["bg"])
    d = ImageDraw.Draw(img)
    _header(img, d, t, 60, 50)
    font, lines, size = _fit(d, joke.setup, F_XBOLD, 1080, 330, 72, 40)
    _draw_block(d, lines, font, size, 60, 180 + (330 - len(lines) * size * 1.22) / 2, t["ink"])
    d.text((60, 560), "Tap for the punchline", font=_font(F_BOLD, 32), fill=t["accent"] if t["name"] != "pop" else t["ink"])
    img.save(path, "JPEG", quality=85)
    return path


def profile_picture(path: Path, size: int = 800) -> Path:
    """Square avatar for Instagram and YouTube."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (size, size), THEMES[0]["accent"])
    m = draw_mascot(size, THEMES[0])
    img.paste(m, (0, 0), m)
    img.save(path, "PNG")
    return path
