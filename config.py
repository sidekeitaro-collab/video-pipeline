import os
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"必須の環境変数 '{name}' が設定されていません。.env またはGitHub Secretsを確認してください。"
        )
    return value


ANTHROPIC_API_KEY = _require_env("ANTHROPIC_API_KEY")
# CreatomateのVoiceover要素がElevenLabsを直接呼ぶため、ElevenLabsアカウント自体は
# Creatomateダッシュボード(Settings > Integrations)側で接続する。ここではVoice IDのみ必要。
ELEVENLABS_VOICE_ID = _require_env("ELEVENLABS_VOICE_ID")
CREATOMATE_API_KEY = _require_env("CREATOMATE_API_KEY")
CREATOMATE_TEMPLATE_ID = _require_env("CREATOMATE_TEMPLATE_ID")
PEXELS_API_KEY = _require_env("PEXELS_API_KEY")
YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secrets.json")

# TikTok / Instagram: 未設定なら該当ステップをスキップ（審査完了後に設定）
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
# PULL_FROM_URL方式はTikTok Developer PortalでのURLプレフィックス検証が別途必要。
# トークンだけ設定されてもこれがtrueになるまでmain.py側で投稿しない。
TIKTOK_DOMAIN_VERIFIED = os.getenv("TIKTOK_DOMAIN_VERIFIED", "").lower() in ("1", "true", "yes")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

# X (旧Twitter): 有料APIプラン契約後に設定。未設定ならスキップ
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

CREATOMATE_API_BASE = "https://api.creatomate.com/v2"
PEXELS_API_BASE = "https://api.pexels.com/videos"

# ショート動画デフォルト設定
VIDEO_ASPECT_RATIO = "9:16"  # ショート向け縦型
