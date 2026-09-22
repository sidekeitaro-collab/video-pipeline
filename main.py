#!/usr/bin/env python3
"""
Short video auto-pipeline:
  Claude (script) → Creatomate (ElevenLabs voiceover + captions + Pexels background) → YouTube / TikTok / Instagram / X
"""
import argparse
import os
import tempfile

from prompt_gen import generate_video_content
from creatomate_render import fetch_background_video, create_render, wait_for_render, download_video
from youtube_upload import upload_to_youtube
from config import (
    TIKTOK_ACCESS_TOKEN,
    TIKTOK_DOMAIN_VERIFIED,
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_TOKEN_SECRET,
)


def run(topic: str, dry_run: bool = False):
    print(f"\n=== PIPELINE START: {topic} ===\n")

    # Step 1: 台本・メタデータ生成
    print("[1/5] Generating script via Claude...")
    content = generate_video_content(topic)
    print(f"  Title: {content['title']}")

    if dry_run:
        print("\n[DRY RUN] Skipping render and upload.")
        print(f"  Content:\n{content}")
        return

    # Step 2: 背景素材検索 (Pexels)
    print("[2/5] Fetching background footage...")
    background_url = fetch_background_video(content["background_query"])

    # Step 3: Creatomateでレンダリング (ElevenLabsナレーション + 字幕自動同期)
    print("[3/5] Rendering video (Creatomate)...")
    render_id = create_render(content["title"], content["script"], background_url)
    video_url = wait_for_render(render_id)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    results = {}
    try:
        download_video(video_url, tmp_path)

        # Step 4: YouTube Shorts へアップロード（失敗したら全体を止める＝フラッグシップ媒体）
        print("[4/5] Uploading to YouTube Shorts...")
        video_id = upload_to_youtube(
            video_path=tmp_path,
            title=content["title"],
            description=content["description"],
            tags=content["tags"],
        )
        results["youtube"] = f"https://youtube.com/shorts/{video_id}"
        print(f"  {results['youtube']}")

        # Step 5: 他媒体へ投稿（資格情報が揃っている場合のみ。1媒体の失敗が他に波及しないようtry/except）
        print("[5/5] Posting to other platforms (if configured)...")

        if TIKTOK_ACCESS_TOKEN and TIKTOK_DOMAIN_VERIFIED:
            try:
                from tiktok_upload import upload_to_tiktok
                results["tiktok"] = upload_to_tiktok(video_url, content["title"])
            except Exception as e:
                results["tiktok"] = f"FAILED: {e}"
                print(f"  [TikTok] ERROR: {e}")
        elif TIKTOK_ACCESS_TOKEN and not TIKTOK_DOMAIN_VERIFIED:
            print("  [TikTok] SKIP (TIKTOK_DOMAIN_VERIFIED未設定 — PULL_FROM_URL用ドメイン検証が先)")
        else:
            print("  [TikTok] SKIP (TIKTOK_ACCESS_TOKEN 未設定 — API審査待ち)")

        if INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID:
            try:
                from instagram_upload import upload_to_instagram
                results["instagram"] = upload_to_instagram(video_url, content["description"])
            except Exception as e:
                results["instagram"] = f"FAILED: {e}"
                print(f"  [Instagram] ERROR: {e}")
        else:
            print("  [Instagram] SKIP (INSTAGRAM_ACCESS_TOKEN 未設定 — API審査待ち)")

        if X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET:
            try:
                from x_upload import upload_to_x
                results["x"] = upload_to_x(tmp_path, content["title"], content["description"])
            except Exception as e:
                results["x"] = f"FAILED: {e}"
                print(f"  [X] ERROR: {e}")
        else:
            print("  [X] SKIP (X_API_KEY等 未設定 — 有料APIプラン未契約)")

        print(f"\n=== DONE: {topic} ===")
        for platform, result in results.items():
            print(f"  {platform}: {result}")
        print()
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Short video auto-pipeline")
    parser.add_argument("topic", help="動画のテーマ (例: '東京の夜景')")
    parser.add_argument("--dry-run", action="store_true", help="動画生成・投稿をスキップして確認のみ")
    args = parser.parse_args()

    run(args.topic, dry_run=args.dry_run)
