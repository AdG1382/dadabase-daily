"""Command line entry point: `python -m dadabase <command>`."""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

from . import captions, config, queue, render, site


def log(msg: str) -> None:
    print(msg, flush=True)


def deploy_site() -> bool:
    """Upload site/ to Cloudflare Pages. Returns False when Cloudflare isn't set up yet."""
    if not (config.CF_API_TOKEN and config.CF_ACCOUNT_ID):
        log("Cloudflare not configured: skipping deploy")
        return False
    env = {**os.environ}
    project = os.environ.get("CF_PAGES_PROJECT", "dadabase-daily")
    subprocess.run(["npx", "--yes", "wrangler@4", "pages", "project", "create", project, "--production-branch", "main"],
                   env=env, capture_output=True)  # fails harmlessly if it already exists
    subprocess.run(["npx", "--yes", "wrangler@4", "pages", "deploy", str(config.SITE_OUT), "--project-name", project,
                    "--branch", "main", "--commit-dirty=true"], env=env, check=True)
    return True


def wait_live(url: str, timeout_s: int = 300) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            if requests.head(url, timeout=15, allow_redirects=True).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise TimeoutError(f"{url} did not go live within {timeout_s}s")


def cmd_post(args) -> int:
    day = queue.today_ist()
    state = queue.load_state()
    joke = queue.pick_next(day, state)
    log(f"[{args.slot}] {joke.id} ({joke.category}, {joke.flavour}, season={joke.season}): {joke.setup}")

    site.build()
    media_dir = config.SITE_OUT / "media" / joke.id.lower()
    results: dict = {}
    errors: list[str] = []

    if args.slot == "carousel":
        slides = render.carousel_slides(joke, media_dir)
        live = False if args.dry_run else deploy_site()
        if config.IG_ACCESS_TOKEN and live and not args.dry_run:
            urls = [f"{config.SITE_URL}/media/{joke.id.lower()}/{p.name}" for p in slides]
            try:
                from . import instagram
                for u in urls:
                    wait_live(u)
                results["ig_id"] = instagram.post_carousel(urls, captions.carousel_caption(joke))
                log(f"Instagram carousel published: {results['ig_id']}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Instagram: {e}")
        else:
            log("Instagram skipped (token or hosting not set up, or dry run)")

    else:  # short: YouTube Short + Instagram Reel from the same video
        from . import video
        mp4 = video.make_short(joke, media_dir)
        live = False if args.dry_run else deploy_site()
        if config.YT_REFRESH_TOKEN and not args.dry_run:
            try:
                from . import youtube
                results["yt_id"] = youtube.upload_short(mp4, captions.youtube_title(joke), captions.youtube_description(joke),
                                                        captions.hashtags(joke, 12))
                log(f"YouTube Short uploaded: https://youtube.com/shorts/{results['yt_id']}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"YouTube: {e}")
        else:
            log("YouTube skipped (not set up yet, or dry run)")
        if config.IG_ACCESS_TOKEN and live and not args.dry_run:
            try:
                from . import instagram
                url = f"{config.SITE_URL}/media/{joke.id.lower()}/{mp4.name}"
                wait_live(url)
                results["ig_reel_id"] = instagram.post_reel(url, captions.reel_caption(joke))
                log(f"Instagram Reel published: {results['ig_reel_id']}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Instagram Reel: {e}")
        else:
            log("Instagram Reel skipped (token or hosting not set up, or dry run)")

    if not args.dry_run:
        if errors:
            results["errors"] = errors
        queue.record(state, joke, args.slot, day, results)
        queue.save_state(state)
    for e in errors:
        log(f"ERROR {e}")
    return 1 if errors else 0


def cmd_build(args) -> int:
    site.build()
    if not args.no_deploy:
        deploy_site()
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
    log(f"Cloudflare: {'configured' if config.CF_API_TOKEN else 'not configured'}")
    return 0


def cmd_avatar(args) -> int:
    log(f"wrote {render.profile_picture(Path(args.out))}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dadabase")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("post", help="pick the next joke, render, publish")
    s.add_argument("--slot", choices=["carousel", "short"], required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_post)
    s = sub.add_parser("build-site")
    s.add_argument("--no-deploy", action="store_true")
    s.set_defaults(fn=cmd_build)
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
