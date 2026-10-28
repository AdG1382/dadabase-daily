"""Generates the static website into site/ (category pages are the main pages Google sees)."""
import html
import json
import shutil
from datetime import date

from . import config, render
from .queue import Joke, live_jokes, load_state

CSS = """
:root{--bg:#FFF8EC;--card:#FFFFFF;--ink:#2E1C12;--muted:#7A5E4C;--line:#EADCC8;--accent:#E8772E;--accent-ink:#FFFFFF;--chip:#FCE7D3}
@media (prefers-color-scheme:dark){:root{--bg:#17120E;--card:#221A14;--ink:#F6ECE2;--muted:#BBA594;--line:#3A2E25;--accent:#F28C45;--accent-ink:#1B120C;--chip:#3A2A1E}}
@font-face{font-family:Inter;src:url(/assets/Inter-Regular.otf);font-weight:400;font-display:swap}
@font-face{font-family:Inter;src:url(/assets/Inter-Bold.otf);font-weight:700;font-display:swap}
@font-face{font-family:Inter;src:url(/assets/Inter-Black.otf);font-weight:900;font-display:swap}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 Inter,system-ui,sans-serif}
a{color:inherit}
.wrap{max-width:880px;margin:0 auto;padding:0 16px}
header.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 0}
.brand{display:flex;align-items:center;gap:10px;white-space:nowrap;text-decoration:none;font-weight:900;letter-spacing:.02em}
.brand img{width:40px;height:40px}
nav.social a{font-weight:700;font-size:15px;text-decoration:none;margin-left:14px;color:var(--muted)}
.hero{padding:28px 0 8px}
.hero h1{font-size:clamp(30px,6vw,48px);line-height:1.1;margin:0 0 8px;font-weight:900}
.hero p{color:var(--muted);margin:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px;margin:18px 0}
.joke .setup{font-size:22px;font-weight:700;margin:0 0 12px}
.joke.big .setup{font-size:clamp(24px,4.5vw,34px);font-weight:900;line-height:1.2}
.reveal{appearance:none;border:0;border-radius:999px;background:var(--accent);color:var(--accent-ink);font:700 15px Inter,sans-serif;padding:10px 18px;cursor:pointer}
.punch{font-size:20px;font-weight:900;color:var(--accent);margin:0}
.joke.big .punch{font-size:clamp(22px,4vw,30px)}
.punch[hidden]{display:none}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:12px 0 28px}
.cat{display:block;text-decoration:none;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;font-weight:700}
.cat span{display:block;font-weight:400;color:var(--muted);font-size:14px}
h2{font-size:24px;margin:34px 0 4px;font-weight:900}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:2px 10px;font-size:13px;font-weight:700;margin-right:6px}
.list .joke{border-top:1px solid var(--line);padding:16px 0}
.list .joke:first-child{border-top:0}
footer{color:var(--muted);font-size:14px;padding:30px 0 40px;border-top:1px solid var(--line);margin-top:30px}
"""

JS = """
document.addEventListener('click',e=>{const b=e.target.closest('[data-reveal]');if(!b)return;
const p=document.getElementById(b.dataset.reveal);if(p){p.hidden=false;b.remove()}});
async function randomJoke(){try{const r=await fetch('/jokes.json');const all=await r.json();
const j=all[Math.floor(Math.random()*all.length)];location.href='/j/'+j.id.toLowerCase()+'/'}catch(e){}}
document.querySelectorAll('[data-random]').forEach(b=>b.addEventListener('click',randomJoke));
"""

PRIVACY = f"""<section class="hero"><h1>Privacy</h1><p>Last updated 28 October 2026</p></section>
<div class="card"><p>{config.BRAND} is a joke website. It has no accounts, no sign-up forms and no comments, and it doesn't
collect personal information from visitors.</p>
<p>The site is hosted on GitHub Pages, which may keep standard server logs (such as IP addresses) for security. See
GitHub's privacy statement for details. No advertising or analytics cookies are used today; if that changes, this page will
say so first.</p>
<p>{config.BRAND} uses the YouTube and Instagram APIs only to publish its own videos and posts to its own channels. It does
not access, store or share anyone else's data. Use of YouTube is subject to the YouTube Terms of Service and the Google Privacy
Policy.</p><p>Questions: message {config.HANDLE} on Instagram.</p></div>"""

CAT_BLURB = {
    "food": "Chai, samosas, biryani and puns that are fully baked.",
    "family": "Dads, moms, aunties and the family WhatsApp group.",
    "work": "Appraisals, meetings and the office chai break.",
    "school": "Exams, results and Sharma ji's son.",
    "sports": "Cricket, gully cricket and a few other sports.",
    "tech": "Wi-Fi, UPI, OTPs and dad's phone.",
    "travel": "Potholes, Mumbai locals and Bengaluru traffic.",
    "weather": "Monsoon, May heat and the 25-degree 'winter'.",
    "festivals": "Diwali, Holi, Christmas and the rest of the calendar.",
    "music": "Bollywood, weddings and antakshari.",
    "animals": "Cows, crows, cats and one very smart fish.",
    "science": "Atoms, planets and no chemistry at all.",
    "puns": "The classics. You have been warned.",
}


def _e(s: str) -> str:
    return html.escape(s, quote=True)


def _page(title: str, body: str, desc: str, path: str, image: str = "", noindex: bool = False) -> str:
    url = f"{config.SITE_URL}{path}"
    img = image or f"{config.SITE_URL}/assets/og.jpg"
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><meta name="description" content="{_e(desc)}">{robots}
<link rel="canonical" href="{url}"><link rel="icon" href="/assets/mascot.png">
<meta property="og:title" content="{_e(title)}"><meta property="og:description" content="{_e(desc)}">
<meta property="og:image" content="{img}"><meta property="og:url" content="{url}"><meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/style.css"></head><body><div class="wrap">
<header class="top"><a class="brand" href="/"><img src="/assets/mascot.png" alt="">{_e(config.BRAND)}</a>
<nav class="social"><a href="{config.INSTAGRAM_URL}">Instagram</a><a href="{config.YOUTUBE_URL}">YouTube</a>{f'<a href="{config.SHOP_URL}">Shop</a>' if config.SHOP_URL else ''}</nav></header>
{body}
<footer>{_e(config.BRAND)} · one dad joke a day, served with chai. Follow <a href="{config.INSTAGRAM_URL}">{_e(config.HANDLE)}</a> on Instagram and YouTube. <a href="/privacy/">Privacy</a></footer>
</div><script>{JS}</script></body></html>"""


def _joke_block(j: Joke, big: bool = False, link: bool = True) -> str:
    pid = f"p-{j.id}"
    setup = f'<a href="/j/{j.id.lower()}/" style="text-decoration:none">{_e(j.setup)}</a>' if link else _e(j.setup)
    return (f'<article class="joke{" big" if big else ""}"><p class="setup">{setup}</p>'
            f'<div class="row"><button class="reveal" data-reveal="{pid}">Show punchline</button></div>'
            f'<p class="punch" id="{pid}" hidden>{_e(j.punchline)}</p></article>')


def build() -> None:
    jokes = live_jokes()
    by_id = {j.id: j for j in jokes}
    state = load_state()
    posted = [by_id[p["id"]] for p in state.get("posted", []) if p.get("published") and p["id"] in by_id]

    if config.SITE_OUT.exists():
        shutil.rmtree(config.SITE_OUT)
    assets = config.SITE_OUT / "assets"
    assets.mkdir(parents=True)
    for f in ("Inter-Regular.otf", "Inter-Bold.otf", "Inter-Black.otf"):
        shutil.copy(config.FONTS / f, assets / f)
    (assets / "style.css").write_text(CSS, encoding="utf-8")
    render.draw_mascot(128).save(assets / "mascot.png")
    if jokes:
        render.share_card(jokes[0], assets / "og.jpg")

    cats: dict[str, list[Joke]] = {}
    for j in jokes:
        cats.setdefault(j.category, []).append(j)
    order = sorted(cats, key=lambda c: -len(cats[c]))

    # Home
    featured = posted[-1] if posted else (jokes[0] if jokes else None)
    grid = "".join(f'<a class="cat" href="/c/{c}/">{_e(render.CATEGORY_LABEL.get(c, c.title()))}<span>{len(cats[c])} jokes</span></a>' for c in order)
    latest = "".join(_joke_block(j) for j in reversed(posted[-8:])) if posted else ""
    body = f"""<section class="hero"><h1>One dad joke a day.<br>Desi, groan-worthy, free.</h1>
<p>{len(jokes)} jokes and counting, with a fresh one on Instagram and YouTube every day.</p></section>
<div class="card">{_joke_block(featured, big=True) if featured else ''}
<div class="row" style="margin-top:14px"><button class="reveal ghost" data-random>Random joke</button></div></div>
<h2>Browse by topic</h2><div class="grid">{grid}</div>
{f'<h2>Recently posted</h2><div class="card list">{latest}</div>' if latest else ''}"""
    (config.SITE_OUT / "index.html").write_text(_page(f"{config.BRAND}: one dad joke a day", body,
        "Desi and classic dad jokes, one a day. Chai, cricket, exams, aunties and the puns your dad loves.", "/"), encoding="utf-8")

    # Category pages (the main pages for search)
    for c in order:
        label = render.CATEGORY_LABEL.get(c, c.title())
        items = "".join(_joke_block(j) for j in cats[c])
        others = " ".join(f'<a class="chip" href="/c/{o}/">{_e(render.CATEGORY_LABEL.get(o, o.title()))}</a>' for o in order if o != c)
        body = (f'<section class="hero"><h1>{_e(label)} dad jokes</h1><p>{_e(CAT_BLURB.get(c, ""))} {len(cats[c])} jokes.</p></section>'
                f'<div class="card list">{items}</div><h2>More topics</h2><p>{others}</p>')
        d = config.SITE_OUT / "c" / c
        d.mkdir(parents=True)
        (d / "index.html").write_text(_page(f"{len(cats[c])} {label} dad jokes | {config.BRAND}", body,
            f"{len(cats[c])} {label.lower()} dad jokes. {CAT_BLURB.get(c, '')}", f"/c/{c}/"), encoding="utf-8")

    # One page per joke (for sharing; kept out of search to avoid thin pages)
    for j in jokes:
        d = config.SITE_OUT / "j" / j.id.lower()
        d.mkdir(parents=True)
        card = render.share_card(j, d / "card.jpg")
        label = render.CATEGORY_LABEL.get(j.category, j.category.title())
        body = (f'<div class="card">{_joke_block(j, big=True, link=False)}</div>'
                f'<div class="row"><button class="reveal ghost" data-random>Another one</button>'
                f'<a class="chip" href="/c/{j.category}/">More {_e(label.lower())} jokes</a></div>')
        (d / "index.html").write_text(_page(f"{j.setup} | {config.BRAND}", body, j.setup, f"/j/{j.id.lower()}/",
            image=f"{config.SITE_URL}/j/{j.id.lower()}/{card.name}", noindex=True), encoding="utf-8")

    (config.SITE_OUT / "jokes.json").write_text(json.dumps([{"id": j.id} for j in jokes]), encoding="utf-8")
    today = date.today().isoformat()
    urls = [f"{config.SITE_URL}/"] + [f"{config.SITE_URL}/c/{c}/" for c in order]
    (config.SITE_OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>\n", encoding="utf-8")
    (config.SITE_OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (config.SITE_OUT / "404.html").write_text(_page("Not found", '<section class="hero"><h1>This joke went missing.</h1><p><a href="/">Back home</a></p></section>', "Not found", "/404", noindex=True), encoding="utf-8")
    priv = config.SITE_OUT / "privacy"
    priv.mkdir()
    (priv / "index.html").write_text(_page(f"Privacy | {config.BRAND}", PRIVACY, f"Privacy policy for {config.BRAND}", "/privacy/"), encoding="utf-8")
    _apply_base_path()
    print(f"Site built: {len(jokes)} jokes, {len(order)} topics")


def _apply_base_path() -> None:
    """Rewrite root-relative links when the site lives under a sub-path (e.g. user.github.io/repo/)."""
    base = config.BASE_PATH
    if not base:
        return
    swaps = [('href="/', f'href="{base}/'), ('src="/', f'src="{base}/'), ("url(/assets", f"url({base}/assets"),
             ("fetch('/jokes.json')", f"fetch('{base}/jokes.json')"), ("location.href='/j/'", f"location.href='{base}/j/'")]
    for f in list(config.SITE_OUT.rglob("*.html")) + [config.SITE_OUT / "assets" / "style.css"]:
        text = f.read_text(encoding="utf-8")
        for a, b in swaps:
            text = text.replace(a, b)
        f.write_text(text, encoding="utf-8")
