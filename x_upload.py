"""
X (旧Twitter) 投稿。

注意: メディア(動画)付き投稿には Basic プラン以上 ($200/月〜) が必要。
X_API_KEY 等が .env に未設定の間は main.py 側でこのモジュールごとスキップされる。
動画アップロードは v1.1 chunked media/upload (OAuth1.0a) → v2 /2/tweets の順で行う。
"""
import time
from retry_utils import request_with_retry
from requests_oauthlib import OAuth1
from config import X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET

UPLOAD_BASE = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_BASE = "https://api.twitter.com/2/tweets"

# Xの文字数カウントはCJK/全角文字を2幅として扱う。ここでは簡易的にEast Asian系レンジを2扱いする
_WIDE_RANGES = [
    (0x1100, 0x115F), (0x2E80, 0xA4CF), (0xAC00, 0xD7A3),
    (0xF900, 0xFAFF), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6),
]
TWEET_MAX_WEIGHT = 280


def _char_weight(ch: str) -> int:
    code = ord(ch)
    return 2 if any(lo <= code <= hi for lo, hi in _WIDE_RANGES) else 1


def truncate_to_tweet_length(text: str, max_weight: int = TWEET_MAX_WEIGHT) -> str:
    weight = 0
    result = []
    for ch in text:
        w = _char_weight(ch)
        if weight + w > max_weight:
            break
        weight += w
        result.append(ch)
    return "".join(result)


def _auth() -> OAuth1:
    return OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)


def upload_to_x(video_path: str, title: str, description: str) -> str:
    text = truncate_to_tweet_length(f"{title}\n\n{description}")

    media_id = _upload_video(video_path)
    _wait_for_processing(media_id)

    resp = request_with_retry(
        "POST",
        TWEET_BASE,
        auth=_auth(),
        json={"text": text, "media": {"media_ids": [media_id]}},
        timeout=30,
    )
    resp.raise_for_status()
    tweet_id = resp.json()["data"]["id"]
    print(f"[X] Posted: https://x.com/i/status/{tweet_id}")
    return tweet_id


def _upload_video(video_path: str) -> str:
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    total_bytes = len(video_bytes)

    init = request_with_retry(
        "POST",
        UPLOAD_BASE,
        auth=_auth(),
        data={"command": "INIT", "media_type": "video/mp4", "total_bytes": total_bytes, "media_category": "tweet_video"},
        timeout=30,
    )
    init.raise_for_status()
    media_id = init.json()["media_id_string"]

    chunk_size = 4 * 1024 * 1024
    for i, offset in enumerate(range(0, total_bytes, chunk_size)):
        chunk = video_bytes[offset : offset + chunk_size]
        append = request_with_retry(
            "POST",
            UPLOAD_BASE,
            auth=_auth(),
            data={"command": "APPEND", "media_id": media_id, "segment_index": i},
            files={"media": ("chunk.mp4", chunk, "application/octet-stream")},
            timeout=60,
        )
        append.raise_for_status()

    finalize = request_with_retry(
        "POST",
        UPLOAD_BASE,
        auth=_auth(),
        data={"command": "FINALIZE", "media_id": media_id},
        timeout=30,
    )
    finalize.raise_for_status()
    print(f"[X] Media uploaded: {media_id}")
    return media_id


def _wait_for_processing(media_id: str, poll_interval: int = 3, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = request_with_retry(
            "GET",
            UPLOAD_BASE,
            auth=_auth(),
            params={"command": "STATUS", "media_id": media_id},
            timeout=15,
        )
        resp.raise_for_status()
        info = resp.json().get("processing_info")
        if not info:
            return  # 処理不要（即時利用可）

        state = info["state"]
        print(f"[X] Processing: {state}")
        if state == "succeeded":
            return
        if state == "failed":
            raise RuntimeError(f"X media processing failed: {media_id}")

        time.sleep(info.get("check_after_secs", poll_interval))

    raise TimeoutError(f"X media {media_id} did not finish processing within {timeout}s")
