"""
MOON TikTok Checker — backend

Why this exists:
  The site's "TikTok Checker" panel needs real video stats/quality data for
  a pasted link. Doing that straight from the browser doesn't work because
  every option has a blocker:
    - Calling TikTok's own API directly: requires signed requests
      (X-Bogus, msToken) and a real browser session — not something a
      static webpage can do.
    - Calling a third-party helper API like tikwm.com: works, but that
      service doesn't send CORS headers, so browsers block it, and public
      CORS-relay proxies (allorigins, codetabs) are unreliable third
      parties you don't control either.

  This backend sidesteps both problems the simple way: it just does a
  plain HTTP GET of the public TikTok video page (the same request your
  own browser makes when you open the link) and reads the JSON TikTok
  already embeds in that page's HTML for its own React app to use. No
  headless browser, no request signing, no third-party scraping API —
  just one HTTP request and CORS headers set on OUR OWN response, so the
  site's frontend can read it directly.

Deploy this anywhere that runs Python (Render, Railway, Fly.io, a small
VPS, PythonAnywhere, etc.) — see README.md in this folder for the ten
minute version. Once it's live, put its URL into TT_BACKEND_URL near the
top of the TikTok Checker script in index.html.

Limits to know about:
  - TikTok changes this embedded-JSON structure occasionally; if that
    happens this needs a small update (both known script tags are
    handled below, which covers TikTok's last two page formats).
  - TikTok may rate-limit or occasionally show a captcha/challenge page
    to a given server IP if it gets a lot of requests very quickly (this
    endpoint does one simple GET per check, same as a person opening the
    link in a browser, so normal personal/small-business use should be
    fine).
  - Private or region-locked videos won't return data — same as if you
    opened the link in an incognito browser and it wasn't viewable.
"""

import json
import re
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)  # Allow the checker to call this from any origin (it's a public read).

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

VIDEO_ID_RE = re.compile(r"/video/(\d+)")

SIGI_TAG_OPEN = '<script id="SIGI_STATE" type="application/json">'
UNIVERSAL_TAG_OPEN = (
    '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
)


def extract_video_id(url: str):
    match = VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


def extract_json_block(html: str, open_tag: str):
    start = html.find(open_tag)
    if start == -1:
        return None
    start += len(open_tag)
    end = html.find("</script>", start)
    if end == -1:
        return None
    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return None


def find_item_struct(html: str, video_id: Optional[str]):
    # TikTok has shipped two different embedded-state formats over time;
    # try the older SIGI_STATE one first, then the newer rehydration one.
    sigi = extract_json_block(html, SIGI_TAG_OPEN)
    if sigi:
        item_module = sigi.get("ItemModule", {})
        if video_id and video_id in item_module:
            return item_module[video_id]
        if item_module:
            return next(iter(item_module.values()))

    universal = extract_json_block(html, UNIVERSAL_TAG_OPEN)
    if universal:
        default_scope = universal.get("__DEFAULT_SCOPE__", {})
        video_detail = default_scope.get("webapp.video-detail", {})
        item_info = video_detail.get("itemInfo", {})
        item = item_info.get("itemStruct")
        if item:
            return item

    return None


@app.route("/api/tiktok")
def tiktok_info():
    link = (request.args.get("url") or "").strip()
    if not link:
        return jsonify({"code": -1, "msg": "missing url parameter"}), 400

    try:
        resp = requests.get(
            link, headers=REQUEST_HEADERS, timeout=15, allow_redirects=True
        )
    except requests.RequestException as exc:
        return jsonify({"code": -1, "msg": f"could not reach TikTok: {exc}"}), 502

    if resp.status_code != 200:
        return (
            jsonify(
                {"code": -1, "msg": f"TikTok returned HTTP {resp.status_code}"}
            ),
            502,
        )

    video_id = extract_video_id(resp.url) or extract_video_id(link)
    item = find_item_struct(resp.text, video_id)
    if item is None:
        return (
            jsonify(
                {
                    "code": -1,
                    "msg": (
                        "couldn't find video data on the page — the link may be "
                        "private, region-locked, deleted, or TikTok's page "
                        "format changed"
                    ),
                }
            ),
            502,
        )

    stats = item.get("statsV2") or item.get("stats") or {}
    video = item.get("video", {})
    author = item.get("author", {})
    music = item.get("music", {})

    def to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    data = {
        "id": item.get("id"),
        "desc": item.get("desc"),
        "createTime": to_int(item.get("createTime")),
        "region": item.get("locationCreated") or None,
        "author": {
            "uniqueId": author.get("uniqueId") if isinstance(author, dict) else author,
            "nickname": author.get("nickname") if isinstance(author, dict) else None,
        },
        "stats": {
            "playCount": to_int(stats.get("playCount")),
            "diggCount": to_int(stats.get("diggCount")),
            "commentCount": to_int(stats.get("commentCount")),
            "shareCount": to_int(stats.get("shareCount")),
            "collectCount": to_int(stats.get("collectCount")),
        },
        "video": {
            "width": video.get("width"),
            "height": video.get("height"),
            "duration": video.get("duration"),
            "bitrate": video.get("bitrate"),
            "definition": video.get("definition"),
            "ratio": video.get("ratio"),
            "playAddr": video.get("playAddr"),
        },
        "music": music.get("title") if isinstance(music, dict) else None,
    }

    return jsonify({"code": 0, "data": data})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
