"""
TikTok Content Posting API (Direct Post, PULL_FROM_URL方式)
https://developers.tiktok.com/doc/content-posting-api-reference-direct-post

前提:
- TIKTOK_ACCESS_TOKEN が .env に設定されていること（未設定ならmain.py側でスキップ）
- 審査完了までは privacy_level=SELF_ONLY のみ投稿可能
- PULL_FROM_URL利用にはCreatomate CDNのURLプレフィックスをTikTok Developer Portalで
  ドメイン所有権検証しておく必要がある（未検証の間はmain.py側でTIKTOK_DOMAIN_VERIFIEDにより
  この関数自体が呼ばれないようゲートされる）
"""
import time
from retry_utils import request_with_retry
from config import TIKTOK_ACCESS_TOKEN

API_BASE = "https://open.tiktokapis.com/v2"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def upload_to_tiktok(video_url: str, title: str, privacy_level: str = "SELF_ONLY") -> str:
    payload = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    resp = request_with_retry(
        "POST", f"{API_BASE}/post/publish/video/init/", headers=_headers(), json=payload, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {data['error']}")

    publish_id = data["data"]["publish_id"]
    print(f"[TikTok] Publish started: {publish_id} (privacy_level={privacy_level})")
    _wait_for_publish(publish_id)
    print(f"[TikTok] Done: {publish_id} (承認後、SELF_ONLYなら本人アカウント上でのみ閲覧可)")
    return publish_id


def _wait_for_publish(publish_id: str, poll_interval: int = 5, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = request_with_retry(
            "POST",
            f"{API_BASE}/post/publish/status/fetch/",
            headers=_headers(),
            json={"publish_id": publish_id},
            timeout=15,
        )
        resp.raise_for_status()
        status = resp.json()["data"]["status"]
        print(f"[TikTok] Status: {status}")

        if status == "PUBLISH_COMPLETE":
            return
        if status == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {publish_id}")

        time.sleep(poll_interval)

    raise TimeoutError(f"TikTok publish {publish_id} did not complete within {timeout}s")
