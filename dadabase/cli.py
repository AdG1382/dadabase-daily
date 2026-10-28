"""Command line entry point: `python -m dadabase <command>`."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from . import captions, config, queue, render, site


def log(msg: str) -> None:
    print(msg, flush=True)


PENDING = config.WORK / "pending.json"


def wait_live(url: str, timeout_s: int = 600) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            if requests.head(url, timeout=15, allow_redirects=True).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise TimeoutError(f"{url} did not go live within {timeout_s}s")


def _gh_output(key: str, value: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def cmd_post(args) -> int:
    """Stage "render": pick a joke, draw its media into site/media, build the site, note it in build/pending.json.
    GitHub Actions then publishes site/ to GitHub Pages.
    Stage "publish": wait for the media URLs, post to Instagram/YouTube, record the result in data/state.json."""
    if args.stage == "render":
        day = queue.today_ist()
        already = any(p.get("published") and p.get("slot") == args.slot and p.get("date") == day.isoformat()
                      for p in queue.load_state().get("posted", []))
        if already and args.skip_if_done:
            log(f"[{args.slot}] already posted today ({day}); nothing to do")
            _gh_output("skip", "true")
            return 0
        _gh_output("skip", "false")
        joke = queue.pick_next(day)
        log(f"[{args.slot}] {joke.id} ({joke.category}, {joke.flavour}, season={joke.season}): {joke.setup}")
        site.build()
        media_dir = config.SITE_OUT / "media" / joke.id.lower()
        if args.slot == "carousel":
            files = [p.name for p in render.carousel_slides(joke, media_dir)]
        else:
            from . import video
            files = [video.make_short(joke, media_dir).name]
        PENDING.write_text(json.dumps({"id": joke.id, "slot": args.slot, "day": day.isoformat(), "files": files}), encoding="utf-8")
        log(f"Rendered {files}; site ready to publish")
        return 0

    # publish
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    joke = {j.id: j for j in queue.load_jokes()}[pending["id"]]
    urls = [f"{config.SITE_URL}/media/{joke.id.lower()}/{f}" for f in pending["files"]]
    results: dict = {}
    errors: list[str] = []

    if args.slot == "carousel":
        if config.IG_ACCESS_TOKEN:
            try:
                from . import instagram
                for u in urls:
                    wait_live(u)
                results["ig_id"] = instagram.post_carousel(urls, captions.carousel_caption(joke))
                log(f"Instagram carousel published: {results['ig_id']}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Instagram: {e}")
        else:
            log("Instagram skipped (no IG_ACCESS_TOKEN secret yet)")
    else:
        mp4 = config.SITE_OUT / "media" / joke.id.lower() / pending["files"][0]
        if config.YT_REFRESH_TOKEN:
            try:
                from . import youtube
                results["yt_id"] = youtube.upload_short(mp4, captions.youtube_title(joke), captions.youtube_description(joke),
                                                        captions.hashtags(joke, 12))
                log(f"YouTube Short uploaded: https://youtube.com/shorts/{results['yt_id']}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"YouTube: {e}")
        else:
            log("YouTube skipped (no YT_REFRESH_TOKEN secret yet)")
        if config.IG_ACCESS_TOKEN:
            try:
                from . import instagram
                wait_live(urls[0])
                results["ig_reel_id"] = instagram.post_reel(urls[0], captions.reel_caption(joke))
                log(f"Instagram Reel published: {results['ig_reel_id']}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Instagram Reel: {e}")
        else:
            log("Instagram Reel skipped (no IG_ACCESS_TOKEN secret yet)")

    if errors:
        results["errors"] = errors
    state = queue.load_state()
    import datetime as dt
    queue.record(state, joke, args.slot, dt.date.fromisoformat(pending["day"]), results)
    queue.save_state(state)
    for e in errors:
        log(f"ERROR {e}")
    return 1 if errors else 0


def cmd_build(args) -> int:
    site.build()
    return 0


def cmd_preview(args) -> int:
    jokes = {j.id: j for j in queue.load_jokes()}
    joke = jokes[args.id] if args.id else queue.pick_next()
    out = Path(args.out)
    for p in render.carousel_slides(joke, out):
        log(f"wrote {p}")
    if args.video:
        from . import video
        log(f"wrote {video.make_short(joke, out)}")
    return 0


def cmd_queue(args) -> int:
    import copy
    import datetime as dt
    state = copy.deepcopy(queue.load_state())
    day = queue.today_ist()
    for i in range(args.count):
        d = day + dt.timedelta(days=i // 2)
        j = queue.pick_next(d, state)
        log(f"{d}  {'AM carousel' if i % 2 == 0 else 'PM short   '}  {j.id}  {j.flavour:<6} {j.category:<9} {j.setup}")
        queue.record(state, j, "sim", d, {"sim_id": "x"})
    return 0


def cmd_refresh_ig_token(args) -> int:
    from . import instagram
    new, secs = instagram.refresh_token(config.IG_ACCESS_TOKEN)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{new}")
    Path(args.out).write_text(new, encoding="utf-8")
    log(f"Instagram token refreshed; valid for about {secs // 86400} days")
    return 0


def cmd_whoami(args) -> int:
    if config.IG_ACCESS_TOKEN:
        from . import instagram
        log(f"Instagram: {instagram.account()}")
    else:
        log("Instagram: no token")
    log(f"YouTube: {'configured' if config.YT_REFRESH_TOKEN else 'not configured'}")
    return 0


def cmd_avatar(args) -> int:
    log(f"wrote {render.profile_picture(Path(args.out))}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dadabase")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("post", help="pick the next joke, render, publish")
    s.add_argument("--slot", choices=["carousel", "short"], required=True)
    s.add_argument("--stage", choices=["render", "publish"], required=True)
    s.add_argument("--skip-if-done", action="store_true", help="exit quietly if this slot already posted today")
    s.set_defaults(fn=cmd_post)
    sub.add_parser("build-site").set_defaults(fn=cmd_build)
    s = sub.add_parser("preview")
    s.add_argument("--id")
    s.add_argument("--out", default="build/preview")
    s.add_argument("--video", action="store_true")
    s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("queue", help="show what will post next")
    s.add_argument("--count", type=int, default=14)
    s.set_defaults(fn=cmd_queue)
    s = sub.add_parser("refresh-ig-token")
    s.add_argument("--out", default="build/ig_token.txt")
    s.set_defaults(fn=cmd_refresh_ig_token)
    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)
    s = sub.add_parser("avatar")
    s.add_argument("--out", default="build/avatar.png")
    s.set_defaults(fn=cmd_avatar)
    args = p.parse_args(argv)
    config.WORK.mkdir(parents=True, exist_ok=True)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
