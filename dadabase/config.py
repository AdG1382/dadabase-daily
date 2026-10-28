"""Central settings. Anything secret comes from environment variables (GitHub secrets)."""
import os
from urllib.parse import urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
SITE_OUT = ROOT / "site"          # generated, never committed
WORK = ROOT / "build"             # scratch, never committed

JOKES_CSV = DATA / "jokes.csv"
STATE_JSON = DATA / "state.json"
SEASONS_JSON = DATA / "seasons.json"

BRAND = "Dadabase Daily"
HANDLE = "@dadabase.daily"
SITE_URL = (os.environ.get("SITE_URL") or "https://adg1382.github.io/dadabase-daily").rstrip("/")
BASE_PATH = urlparse(SITE_URL).path.rstrip("/")   # "/dadabase-daily" on github.io, "" on a custom domain
INSTAGRAM_URL = "https://www.instagram.com/dadabase.daily/"
YOUTUBE_URL = "https://www.youtube.com/@dadabasedaily"
SHOP_URL = os.environ.get("SHOP_URL") or ""   # fill in once a merch store exists

TIMEZONE = "Asia/Kolkata"

# Secrets (empty = that platform is skipped, so the pipeline can run before setup is finished)
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_API_VERSION = os.environ.get("IG_API_VERSION", "v26.0")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN", "")
YT_PRIVACY = os.environ.get("YT_PRIVACY") or "public"

TTS_VOICE = os.environ.get("TTS_VOICE", "en-IN-PrabhatNeural")
