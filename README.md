# Short Video Auto-Pipeline

Claude (台本生成) → Creatomate (ElevenLabsナレーション + 字幕自動同期 + Pexels背景素材) → YouTube Shorts / TikTok / Instagram Reels / X

GitHub Actionsの日次cronで完全自動化。

## アーキテクチャ

```
[GitHub Actions Cron 日次]
   → Claude API: 台本(script) + 背景検索クエリ + タイトル/タグ JSON生成   (prompt_gen.py)
   → Pexels API: background_query で縦型b-roll素材を検索               (creatomate_render.py)
   → Creatomate API: template_id に Voiceover(script)/Background を流し込みレンダリング
                      ナレーションはCreatomate内蔵のElevenLabs連携で生成
                      字幕はtranscript_sourceでナレーションに自動同期     (creatomate_render.py)
   → 完成mp4をダウンロード
   → YouTube Shorts へアップロード                                     (youtube_upload.py)
   → TikTok / Instagram / X へアップロード（資格情報が揃っていれば）    (tiktok_upload.py / instagram_upload.py / x_upload.py)
```

## セットアップ

```bash
cd ~/video-pipeline
pip install -r requirements.txt
cp .env.example .env
# .env にAPIキーを記入
```

### 必須の手動作業

1. **Creatomateテンプレート作成**
   - https://creatomate.com でアカウント作成
   - Web UIで9:16テンプレートを作成し、以下の要素を用意:
     - `Title`（テキスト要素）
     - `Voiceover-1`（audio要素。ElevenLabsを`provider`に設定 — Creatomate側の連携設定に従う）
     - 上記に`transcript_source: "Voiceover-1"`を紐付けたテキスト要素（字幕自動同期）
     - `Background`（video要素、動的に差し替え）
   - テンプレート保存後の`template_id`を`.env`の`CREATOMATE_TEMPLATE_ID`に設定

2. **ElevenLabsボイス選定**
   - https://elevenlabs.io で日本語ボイスを試聴し、Voice IDを`.env`の`ELEVENLABS_VOICE_ID`に設定
   - ElevenLabsアカウント自体はCreatomate側（Settings > Integrations等）で接続

3. **Pexels APIキー取得**（無料）
   - https://www.pexels.com/api/ で取得 → `.env`の`PEXELS_API_KEY`

4. **YouTube OAuth**（既存手順を流用）
   - Google Cloud Console → YouTube Data API v3 有効化 → OAuth 2.0クライアントID（デスクトップ）作成
   - `client_secrets.json`をダウンロードしてプロジェクトルートに配置
   - 初回のみ`python main.py "テスト" --dry-run`ではなく本番実行でブラウザ認証 → `youtube_token.json`が生成される

5. **TikTok / Instagram**（審査完了後）
   - `api-applications/`のチェックリストに沿って申請
   - 承認後、`TIKTOK_ACCESS_TOKEN` / `INSTAGRAM_ACCESS_TOKEN` / `INSTAGRAM_BUSINESS_ACCOUNT_ID`を設定するまでは自動でスキップされる
   - TikTokはトークン設定に加え、PULL_FROM_URL用にCreatomate CDNのURLプレフィックスをTikTok Developer Portalでドメイン検証したうえで`TIKTOK_DOMAIN_VERIFIED=true`も設定する必要がある（どちらか片方だけではスキップされる）

6. **X**（任意・要検討）
   - 自動投稿には有料APIプラン(Basic $200/月〜)が必要。費用対効果を見て契約するか判断
   - `X_API_KEY`等が未設定の間はスキップされる

## 使い方（ローカル）

```bash
# 動作確認（Claudeの台本生成のみ、レンダリング・投稿なし）
python main.py "東京の夜景" --dry-run

# 本番実行
python main.py "知ると怖い日常の雑学"
```

## GitHub Actionsでの自動化

`.github/workflows/daily_post.yml` が毎日21:00 JSTに自動実行（`workflow_dispatch`で手動実行も可）。

### 必要なGitHub Secrets

| Secret | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API |
| `ELEVENLABS_VOICE_ID` | ElevenLabsで選定したVoice ID |
| `CREATOMATE_API_KEY` / `CREATOMATE_TEMPLATE_ID` | Creatomate |
| `PEXELS_API_KEY` | Pexels |
| `YOUTUBE_TOKEN_JSON` | ローカルで生成した`youtube_token.json`の中身をそのまま貼り付け |
| `YOUTUBE_CLIENT_SECRETS_JSON` | `client_secrets.json`の中身をそのまま貼り付け |
| `TIKTOK_ACCESS_TOKEN` / `TIKTOK_DOMAIN_VERIFIED` | 審査完了後（任意）。両方揃って初めて投稿される |
| `INSTAGRAM_ACCESS_TOKEN` / `INSTAGRAM_BUSINESS_ACCOUNT_ID` | 審査完了後（任意） |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | 有料プラン契約後（任意） |

## ファイル構成

```
video-pipeline/
├── main.py                  # メインパイプライン
├── prompt_gen.py             # Claudeによる台本・メタデータ生成
├── creatomate_render.py       # Pexels背景検索 + Creatomateレンダリング
├── retry_utils.py             # 一時的なネットワークエラーのリトライ共通処理
├── youtube_upload.py          # YouTube Shorts アップロード
├── tiktok_upload.py           # TikTok Content Posting API（審査完了後有効化）
├── instagram_upload.py        # Instagram Graph API（審査完了後有効化）
├── x_upload.py                # X API v2（有料プラン契約後有効化）
├── config.py                  # 設定
├── requirements.txt
├── .env.example
├── .github/workflows/daily_post.yml  # 日次cron
└── api-applications/          # Instagram / TikTok API 申請資料
    ├── privacy-policy.md
    ├── tiktok-checklist.md
    └── instagram-checklist.md
```
