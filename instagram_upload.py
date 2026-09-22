"""
Instagram Graph API — Reels投稿
https://developers.facebook.com/docs/instagram-platform/content-publishing

前提: INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_BUSINESS_ACCOUNT_ID が .env に設定されていること
（未設定ならmain.py側でスキップ）。Businessアカウント + Facebookページ連携が必須。
"""
import time
from retry_utils import request_with_retry
from config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

API_BASE = "https://graph.facebook.com/v19.0"


def upload_to_instagram(video_url: str, caption: str) -> str:
    # Step 1: メディアコンテナ作成
    resp = request_with_retry(
        "POST",
        f"{API_BASE}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    creation_id = resp.json()["id"]
    print(f"[Instagram] Container created: {creation_id}")

    _wait_for_container_ready(creation_id)

    # Step 2: 公開
    resp = request_with_retry(
        "POST",
        f"{API_BASE}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish",
        params={"creation_id": creation_id, "access_token": INSTAGRAM_ACCESS_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    print(f"[Instagram] Published: {media_id}")
    return media_id


def _wait_for_container_ready(creation_id: str, poll_interval: int = 5, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = request_with_retry(
            "GET",
            f"{API_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": INSTAGRAM_ACCESS_TOKEN},
            timeout=15,
        )
        resp.raise_for_status()
        status = resp.json()["status_code"]
        print(f"[Instagram] Status: {status}")

        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram container processing failed: {creation_id}")

        time.sleep(poll_interval)

    raise TimeoutError(f"Instagram container {creation_id} did not become ready within {timeout}s")
