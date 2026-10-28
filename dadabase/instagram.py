"""Instagram posting through the official Instagram API (Instagram Login)."""
import time

import requests

from . import config

BASE = "https://graph.instagram.com"


def _h():
    return {"Authorization": f"Bearer {config.IG_ACCESS_TOKEN}"}


def _url(path: str) -> str:
    return f"{BASE}/{config.IG_API_VERSION}/{path.lstrip('/')}"


def _check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram API error {r.status_code}: {data.get('error', data)}")
    return data


def account() -> dict:
    data = _check(requests.get(_url("me"), params={"fields": "user_id,username"}, headers=_h(), timeout=30))
    return {"id": data.get("user_id") or data["id"], "username": data.get("username", "")}


def _wait_ready(container_id: str, timeout_s: int = 600) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        data = _check(requests.get(_url(container_id), params={"fields": "status_code,status"}, headers=_h(), timeout=30))
        code = data.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process media {container_id}: {data}")
        time.sleep(8)
    raise TimeoutError(f"Instagram media {container_id} still processing after {timeout_s}s")


def _publish(ig_id: str, creation_id: str) -> str:
    data = _check(requests.post(_url(f"{ig_id}/media_publish"), data={"creation_id": creation_id}, headers=_h(), timeout=60))
    return data["id"]


def post_carousel(image_urls: list[str], caption: str) -> str:
    ig = account()["id"]
    children = []
    for u in image_urls:
        c = _check(requests.post(_url(f"{ig}/media"), data={"image_url": u, "is_carousel_item": "true"}, headers=_h(), timeout=60))
        children.append(c["id"])
    for c in children:
        _wait_ready(c)
    parent = _check(requests.post(_url(f"{ig}/media"), data={
        "media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}, headers=_h(), timeout=60))
    _wait_ready(parent["id"])
    return _publish(ig, parent["id"])


def post_reel(video_url: str, caption: str) -> str:
    ig = account()["id"]
    c = _check(requests.post(_url(f"{ig}/media"), data={
        "media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}, headers=_h(), timeout=60))
    _wait_ready(c["id"], timeout_s=900)
    return _publish(ig, c["id"])


def refresh_token(token: str) -> tuple[str, int]:
    """Swap a long-lived token for a fresh 60-day one. Returns (token, seconds_valid)."""
    r = requests.get(f"{BASE}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
    data = _check(r)
    return data["access_token"], int(data.get("expires_in", 0))
