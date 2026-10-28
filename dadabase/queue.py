"""Loads jokes and posting history, and decides which joke goes out next."""
import csv
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, asdict

from . import config


@dataclass
class Joke:
    id: str
    setup: str
    punchline: str
    category: str
    flavour: str   # "India" or "Global"
    season: str    # "any" or a key from seasons.json
    status: str    # "" or "cut"

    @property
    def index(self) -> int:
        return int(self.id[2:])

    def to_dict(self):
        return asdict(self)


def load_jokes() -> list[Joke]:
    with open(config.JOKES_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    jokes = []
    for r in rows:
        if not r.get("id") or not r.get("setup"):
            continue
        jokes.append(Joke(
            id=r["id"].strip(), setup=r["setup"].strip(), punchline=r["punchline"].strip(),
            category=(r.get("category") or "puns").strip().lower(),
            flavour=(r.get("flavour") or "Global").strip(),
            season=(r.get("season") or "any").strip().lower(),
            status=(r.get("status") or "").strip().lower(),
        ))
    return jokes


def live_jokes() -> list[Joke]:
    """Jokes that are allowed anywhere (not cut)."""
    return [j for j in load_jokes() if j.status != "cut"]


def load_state() -> dict:
    if config.STATE_JSON.exists():
        return json.loads(config.STATE_JSON.read_text(encoding="utf-8"))
    return {"posted": []}


def save_state(state: dict) -> None:
    config.STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def today_ist() -> dt.date:
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo(config.TIMEZONE)).date()


def active_seasons(day: dt.date) -> set[str]:
    data = json.loads(config.SEASONS_JSON.read_text(encoding="utf-8"))
    active = set()
    md = day.strftime("%m-%d")
    for name, windows in data.get("yearly", {}).items():
        for start, end in windows:
            # windows may wrap around the new year (e.g. 12-27 to 01-07)
            if (start <= end and start <= md <= end) or (start > end and (md >= start or md <= end)):
                active.add(name)
    iso = day.isoformat()
    for name, windows in data.get("dated", {}).items():
        for start, end in windows:
            if start <= iso <= end:
                active.add(name)
    return active


def _shuffle_key(joke: Joke) -> str:
    # Stable pseudo-random order, so the feed doesn't follow the CSV's category order.
    return hashlib.sha1(f"dadabase:{joke.id}".encode()).hexdigest()


def pick_next(day: dt.date | None = None, state: dict | None = None) -> Joke:
    """Next joke to post.

    Rules: never repeat until every live joke has posted once; seasonal jokes only post
    inside their window and go first while it is open; alternate India/Global flavour and
    avoid repeating the last category when possible.
    """
    day = day or today_ist()
    state = state if state is not None else load_state()
    jokes = live_jokes()
    if not jokes:
        raise RuntimeError("No live jokes left in data/jokes.csv")
    seasons = active_seasons(day)

    posted_ids = [p["id"] for p in state.get("posted", []) if p.get("published")]
    counts: dict[str, int] = {}
    for pid in posted_ids:
        counts[pid] = counts.get(pid, 0) + 1

    def eligible_by_season(j: Joke) -> bool:
        return j.season == "any" or j.season in seasons

    pool = [j for j in jokes if eligible_by_season(j)]
    # Fewest posts first: everything posts once before anything repeats.
    min_count = min(counts.get(j.id, 0) for j in pool)
    pool = [j for j in pool if counts.get(j.id, 0) == min_count]

    by_id = {j.id: j for j in jokes}
    last = by_id.get(posted_ids[-1]) if posted_ids else None
    recent = set(posted_ids[-30:])

    # At most one seasonal joke a day, so a festival's jokes spread across its window.
    seasonal_today = any(
        p.get("date") == day.isoformat() and by_id.get(p["id"]) is not None and by_id[p["id"]].season != "any"
        for p in state.get("posted", []) if p.get("published")
    )

    def score(j: Joke):
        in_season = j.season != "any" and j.season in seasons
        return (
            0 if in_season and not seasonal_today else (2 if in_season else 1),  # one in-season joke per day
            0 if j.id not in recent else 1,                                 # not shown lately
            0 if (last is None or j.flavour != last.flavour) else 1,       # alternate flavour
            0 if (last is None or j.category != last.category) else 1,     # vary category
            _shuffle_key(j),
        )

    return min(pool, key=score)


def record(state: dict, joke: Joke, slot: str, day: dt.date, results: dict) -> None:
    published = any(v for k, v in results.items() if k.endswith("_id"))
    state.setdefault("posted", []).append({
        "id": joke.id, "slot": slot, "date": day.isoformat(), "published": published, **results,
    })
