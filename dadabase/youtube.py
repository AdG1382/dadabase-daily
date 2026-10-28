"""YouTube Shorts upload through the YouTube Data API v3 (resumable upload)."""
import json
from pathlib import Path

import requests

from . import config


def _access_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": config.YT_CLIENT_ID, "client_secret": config.YT_CLIENT_SECRET,
        "refresh_token": config.YT_REFRESH_TOKEN, "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Google token refresh failed ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def upload_short(video: Path, title: str, description: str, tags: list[str]) -> str:
    token = _access_token()
    meta = {
        "snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:15], "categoryId": "23"},  # 23 = Comedy
        "status": {"privacyStatus": config.YT_PRIVACY, "selfDeclaredMadeForKids": False},
    }
    size = video.stat().st_size
    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(meta), timeout=60)
    if init.status_code != 200:
        raise RuntimeError(f"YouTube upload start failed ({init.status_code}): {init.text[:500]}")
    with open(video, "rb") as f:
        up = requests.put(init.headers["Location"], data=f,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4", "Content-Length": str(size)},
                          timeout=600)
    if up.status_code not in (200, 201):
        raise RuntimeError(f"YouTube upload failed ({up.status_code}): {up.text[:500]}")
    return up.json()["id"]
