"""Opens a GitHub issue when posting breaks, and closes it once posting works again.

GitHub notifies the repo owner about new issues (email, and push on the GitHub mobile app), so a
broken token is noticed in hours instead of days. Uses the workflow's built-in GITHUB_TOKEN.
"""
import os

import requests

API = "https://api.github.com"

ALERTS = {
    "instagram_token": {
        "title": "Instagram token stopped working: regenerate it",
        "body": (
            "Instagram rejected the access token, so Instagram posts are failing.\n\n"
            "**Fix (2 minutes):**\n"
            "1. Open the Meta app → Instagram API → *API setup with Instagram login* → "
            "**Generate token** next to dadabase.daily, log in and allow.\n"
            "2. Paste it into this repo: Settings → Secrets and variables → Actions → "
            "`IG_ACCESS_TOKEN` → Update.\n"
            "3. Optional: Actions → *Post daily joke* → Run workflow, to post today straight away.\n\n"
            "This issue closes itself after the next successful Instagram post."
        ),
    },
    "youtube_token": {
        "title": "YouTube login stopped working: re-run the token script",
        "body": (
            "Google rejected the YouTube refresh token, so Shorts are not uploading.\n\n"
            "**Fix:** on your computer run `python scripts/get_youtube_token.py CLIENT_ID CLIENT_SECRET`, "
            "sign in as the channel account, and paste the printed token into the `YT_REFRESH_TOKEN` secret.\n\n"
            "This issue closes itself after the next successful YouTube upload."
        ),
    },
    "other": {
        "title": "Daily post failed",
        "body": "A daily post failed for a reason other than an expired login. Details are in the comments below "
                "and in the Actions run log.\n\nThis issue closes itself after the next fully successful post.",
    },
}


def classify(error: str) -> str:
    e = error.lower()
    if e.startswith("instagram") and ("code': 190" in e or "error 401" in e or "access token" in e):
        return "instagram_token"
    if e.startswith("youtube") and ("invalid_grant" in e or "token refresh failed" in e or "401" in e):
        return "youtube_token"
    return "other"


def _ctx():
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return None
    return repo, {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _open_issue(repo, h, title):
    r = requests.get(f"{API}/repos/{repo}/issues", headers=h, params={"state": "open", "per_page": 100}, timeout=30)
    r.raise_for_status()
    return next((i for i in r.json() if i.get("title") == title and "pull_request" not in i), None)


def _run_link() -> str:
    server, repo, run = os.environ.get("GITHUB_SERVER_URL"), os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_RUN_ID")
    return f"{server}/{repo}/actions/runs/{run}" if server and repo and run else ""


def raise_alert(kind: str, detail: str) -> None:
    ctx = _ctx()
    if not ctx:
        return
    repo, h = ctx
    spec = ALERTS[kind]
    note = f"Failed again: {detail[:600]}\n\n{_run_link()}".strip()
    try:
        existing = _open_issue(repo, h, spec["title"])
        if existing:
            requests.post(f"{API}/repos/{repo}/issues/{existing['number']}/comments", headers=h,
                          json={"body": note}, timeout=30)
        else:
            requests.post(f"{API}/repos/{repo}/issues", headers=h,
                          json={"title": spec["title"], "body": spec["body"] + "\n\n---\n" + note}, timeout=30).raise_for_status()
            print(f"Opened alert issue: {spec['title']}")
    except requests.RequestException as e:  # an alert failing must never break posting
        print(f"Could not open alert issue: {e}")


def resolve(kind: str) -> None:
    ctx = _ctx()
    if not ctx:
        return
    repo, h = ctx
    try:
        existing = _open_issue(repo, h, ALERTS[kind]["title"])
        if existing:
            n = existing["number"]
            requests.post(f"{API}/repos/{repo}/issues/{n}/comments", headers=h,
                          json={"body": f"Working again. Closing automatically. {_run_link()}"}, timeout=30)
            requests.patch(f"{API}/repos/{repo}/issues/{n}", headers=h, json={"state": "closed"}, timeout=30)
            print(f"Closed alert issue: {ALERTS[kind]['title']}")
    except requests.RequestException as e:
        print(f"Could not close alert issue: {e}")


def report(errors: list[str], succeeded: set[str]) -> None:
    """errors: messages from this run; succeeded: platforms that worked ("instagram", "youtube")."""
    for err in errors:
        raise_alert(classify(err), err)
    if "instagram" in succeeded:
        resolve("instagram_token")
    if "youtube" in succeeded:
        resolve("youtube_token")
    if not errors and succeeded:
        resolve("other")
