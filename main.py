#!/usr/bin/env python3
"""
Daily fashion lookbook video pipeline orchestrator:

  theme_gen (Claude: 本日のテーマ+7ルック分の服装差分)
    → generate_looks (Gemini: ベース画像+7ルック画像)
    → assemble_video (ffmpeg+Pillow: 9:16動画に合成)
    → public/videos/YYYY-MM-DD.mp4 としてリポジトリにcommit・push
    → YouTube Shorts へアップロード(本日分)
    → 未投稿バックログがあれば、最も古い1本も合わせてYouTubeへアップロード
      (一度に大量投稿せず1日1本ずつ消化する。logs/youtube-posted.jsonで追跡)

TikTok/Instagram/Xは審査待ちでSecrets未設定のため、今回はまだ組み込まない
(Secretsが揃い次第、YouTubeと同様のスキップ可能なステップとして追加する想定)。
"""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from theme_gen import generate_theme
from generate_looks import generate_all_looks
from assemble_video import assemble

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATED_ROOT = os.path.join(REPO_ROOT, "generated", "daily")
OUTPUT_DIR = os.path.join(REPO_ROOT, "output")
PUBLIC_VIDEOS_DIR = os.path.join(REPO_ROOT, "public", "videos")
BGM_PATH = os.path.join(REPO_ROOT, "assets", "bgm", "chill-lofi.mp3")
HISTORY_PATH = os.path.join(REPO_ROOT, "logs", "theme-history.json")
POSTED_LOG_PATH = os.path.join(REPO_ROOT, "logs", "youtube-posted.json")

GITHUB_REPO = "sidekeitaro-collab/video-pipeline"
JST = ZoneInfo("Asia/Tokyo")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"必須の環境変数 '{name}' が設定されていません。GitHub Secretsを確認してください。"
        )
    return value


def _run_git(*args: str) -> None:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")


def _ensure_git_identity() -> None:
    """コミット用のgit identityが未設定(CIランナーのデフォルト状態)なら、
    このリポジトリ限定(--globalではない)で設定する。"""
    for key, value in (
        ("user.name", "video-pipeline-bot"),
        ("user.email", "video-pipeline-bot@users.noreply.github.com"),
    ):
        current = subprocess.run(
            ["git", "config", key], cwd=REPO_ROOT, capture_output=True, text=True
        )
        if not current.stdout.strip():
            _run_git("config", key, value)


def _load_posted_dates() -> list[str]:
    if not os.path.exists(POSTED_LOG_PATH):
        return []
    with open(POSTED_LOG_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


def _save_posted_dates(dates: list[str]) -> None:
    os.makedirs(os.path.dirname(POSTED_LOG_PATH) or ".", exist_ok=True)
    with open(POSTED_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(set(dates)), f, ensure_ascii=False, indent=2)


def _theme_for_date(date_str: str) -> str:
    """logs/theme-history.jsonからdate_strに対応するitem_themeを引く。見つからなければ
    (theme_gen.pyの日付がUTC基準だった旧データとのズレ等)日付自体をフォールバックにする。"""
    if not os.path.exists(HISTORY_PATH):
        return date_str
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        try:
            history = json.load(f)
        except json.JSONDecodeError:
            return date_str
    for entry in history if isinstance(history, list) else []:
        if entry.get("date") == date_str:
            return entry.get("item_theme", date_str)
    return date_str


def find_backlog_video(exclude_date: str) -> tuple[str, str, str] | None:
    """public/videos/配下の未投稿(YouTube)バックログのうち、最も古い1本を返す。
    (動画パス, 日付文字列, テーマ名) のタプル。無ければNone。"""
    if not os.path.isdir(PUBLIC_VIDEOS_DIR):
        return None

    posted = set(_load_posted_dates())
    candidates = []
    for filename in os.listdir(PUBLIC_VIDEOS_DIR):
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.mp4", filename)
        if not match:
            continue
        date_str = match.group(1)
        if date_str == exclude_date or date_str in posted:
            continue
        candidates.append(date_str)

    if not candidates:
        return None

    oldest = sorted(candidates)[0]
    return os.path.join(PUBLIC_VIDEOS_DIR, f"{oldest}.mp4"), oldest, _theme_for_date(oldest)


def publish_video(video_path: str, date_str: str, item_theme: str) -> str:
    """完成動画をpublic/videos/YYYY-MM-DD.mp4としてコミット・pushし、rawのURLを返す。"""
    os.makedirs(PUBLIC_VIDEOS_DIR, exist_ok=True)
    public_path = os.path.join(PUBLIC_VIDEOS_DIR, f"{date_str}.mp4")
    with open(video_path, "rb") as src, open(public_path, "wb") as dst:
        dst.write(src.read())

    _ensure_git_identity()
    # 重複回避に使うテーマ履歴も、CIランナーが毎回使い捨てのため同じコミットで書き戻す。
    _run_git("add", public_path, HISTORY_PATH)
    _run_git("commit", "-m", f"Daily video: {item_theme} ({date_str})")
    _run_git("push")

    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/public/videos/{date_str}.mp4"


def _youtube_credentials_available() -> bool:
    client_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secrets.json")
    token_file = "youtube_token.json"
    return (
        os.path.exists(client_secrets) and os.path.getsize(client_secrets) > 0
        and os.path.exists(token_file) and os.path.getsize(token_file) > 0
    )


def upload_to_youtube_shorts(video_path: str, item_theme: str) -> None:
    title = f"本日のコーデ紹介【{item_theme}】"
    description = f"今日のテーマは「{item_theme}」。7パターンのコーディネートをご紹介します。"
    tags = ["ファッション", "コーデ", "メンズファッション", item_theme]

    from youtube_upload import upload_to_youtube

    video_id = upload_to_youtube(
        video_path=video_path, title=title, description=description, tags=tags
    )
    print(f"  [YouTube] https://youtube.com/shorts/{video_id}")


def run(dry_run: bool = False) -> None:
    date_str = datetime.now(JST).strftime("%Y-%m-%d")

    print(f"\n=== DAILY VIDEO PIPELINE START: {date_str} ===\n")

    print("[1/4] Generating today's theme (Claude)...")
    anthropic_api_key = _require_env("ANTHROPIC_API_KEY")
    theme = generate_theme(anthropic_api_key, history_path=HISTORY_PATH, date_str=date_str)
    print(f"  Theme: {theme['item_theme']}")

    print("[2/4] Generating look images (Gemini)...")
    gemini_api_key = _require_env("GEMINI_API_KEY")
    output_dir = os.path.join(GENERATED_ROOT, date_str)
    base_path, look_paths = generate_all_looks(gemini_api_key, theme, output_dir)
    print(f"  Generated {len(look_paths)} looks (base: {base_path})")

    print("[3/4] Assembling video (ffmpeg)...")
    bgm_path = BGM_PATH if os.path.exists(BGM_PATH) else None
    video_path = os.path.join(OUTPUT_DIR, f"{date_str}.mp4")
    assemble(theme, look_paths, bgm_path, video_path)
    print(f"  Assembled: {video_path}")

    if dry_run:
        print("\n[DRY RUN] Skipping publish (git push) and upload.")
        print(f"\n=== DONE (dry-run): {date_str} ===\n")
        return

    print("[4/4] Publishing & uploading...")
    video_url = publish_video(video_path, date_str, theme["item_theme"])
    print(f"  Published: {video_url}")

    posted_dates = _load_posted_dates()

    # YouTubeはフラッグシップ媒体のため、失敗したら例外をそのまま伝播させて
    # ワークフローを失敗として可視化する(黙って握りつぶさない)。
    if _youtube_credentials_available():
        upload_to_youtube_shorts(video_path, theme["item_theme"])
        posted_dates.append(date_str)

        # 過去に生成したが投稿し損ねたバックログを、1日1本ずつ消化する
        # (まとめて大量投稿しない)。
        backlog = find_backlog_video(exclude_date=date_str)
        if backlog:
            backlog_path, backlog_date, backlog_theme = backlog
            print(f"[backlog] Uploading leftover video from {backlog_date} ({backlog_theme})...")
            upload_to_youtube_shorts(backlog_path, backlog_theme)
            posted_dates.append(backlog_date)
        else:
            print("[backlog] No unposted backlog videos.")

        _save_posted_dates(posted_dates)
        _ensure_git_identity()
        _run_git("add", POSTED_LOG_PATH)
        # 投稿ログ以外に差分が無いこともあるため、commitが空になる場合はスキップする。
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT
        )
        if status.returncode != 0:
            _run_git("commit", "-m", f"Update youtube-posted log ({date_str})")
            _run_git("push")
    else:
        print("  [YouTube] SKIP (認証情報未設定)")

    print(f"\n=== DONE: {date_str} ===\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily fashion lookbook video pipeline")
    parser.add_argument(
        "--dry-run", action="store_true", help="動画生成のみ行い、git push・投稿はスキップ"
    )
    args = parser.parse_args()

    run(dry_run=args.dry_run)
