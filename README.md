# Short Video Auto-Pipeline

Claude (本日のテーマ+7ルック分の服装差分を生成) → Gemini / Nano Banana 2 (キャラクター一貫性のあるルックブック画像を生成) → ffmpeg (9:16スライドショー動画に合成) → YouTube Shorts / TikTok / Instagram / X

GitHub Actionsの日次cronで完全自動化。外部の有料動画レンダリングサービス(Creatomate等)は不使用——動画合成はffmpeg(GitHub Actions runner上、追加コストゼロ)で完結する。

## アーキテクチャ

```
[GitHub Actions Cron 日次]
   → Claude API: 本日のアイテムテーマ+7ルック分の服装差分(色/ボトムス/小物)をJSON生成
                 キャラ設定・背景・構図等の技術指定はコード側固定テンプレート        (theme_gen.py)
                 直近30件のテーマ履歴を避けて重複を防止                        (logs/theme-history.json)
   → Gemini API (Nano Banana 2 / gemini-3.1-flash-image, Interactions API):
                 架空モデルのベース参照画像を1枚生成 → それを参照に服だけ差し替えた
                 7ルック画像を生成(image-to-image)                          (generate_looks.py)
   → Pillow: 各画像に商品名+LOOK表記のテキストオーバーレイを焼き込み
   → ffmpeg (concat demuxer): 7枚を各0.9秒ハードカットで連結、BGM(Pixabay
                 「Chill Lofi」)をミックスして9:16 mp4を出力                  (assemble_video.py)
   → 完成動画を public/videos/YYYY-MM-DD.mp4 としてリポジトリにcommit・push
                 (Instagram/TikTokの投稿APIが要求する公開HTTPS URLを得るため)   (main.py)
   → YouTube Shorts へ直接アップロード                                      (youtube_upload.py)
   → TikTok / Instagram / X へアップロード（資格情報が揃っていれば、未設定ならスキップ）
```

参考画像収集(Pinterest)は現状パイプライン本体には未接続——`pinterest_reference.py`単体で検証済みの独立モジュール(将来、テーマ生成や画像生成の参考素材として組み込む余地あり)。

## セットアップ

```bash
cd ~/video-pipeline
pip install -r requirements.txt
cp .env.example .env
# .env にAPIキーを記入
```

### 必須の手動作業

1. **Anthropic APIキー取得**
   - https://console.anthropic.com で取得 → `.env`の`ANTHROPIC_API_KEY`

2. **Google Gemini APIキー取得**
   - https://aistudio.google.com/apikey で取得 → `.env`の`GEMINI_API_KEY`
   - `gemini-3.1-flash-image`はFree Tierでは使用不可(1日0リクエスト)。Google AI Studio側で課金(Billing)を有効化する必要がある
   - 目安コスト: 1K画像1枚≈$0.067。1日8枚(ベース+7ルック)≈$0.54、月次cronで毎日実行した場合≈$16/月

3. **YouTube OAuth**（既存手順を流用）
   - Google Cloud Console → YouTube Data API v3 有効化 → OAuth 2.0クライアントID（デスクトップ）作成
   - `client_secrets.json`をダウンロードしてプロジェクトルートに配置
   - 初回のみ`python main.py --dry-run`ではなく本番実行でブラウザ認証 → `youtube_token.json`が生成される

4. **TikTok / Instagram**（審査完了後、現状パイプライン未接続）
   - `api-applications/`のチェックリストに沿って申請
   - 承認・実装完了後、対応するSecretsを設定するまでは自動でスキップされる想定

5. **X**（任意・要検討）
   - 自動投稿には有料APIプラン(Basic $200/月〜)が必要。費用対効果を見て契約するか判断

## 使い方（ローカル）

```bash
# 動作確認（テーマ生成・画像生成・動画合成は実行、git push・投稿はスキップ）
python main.py --dry-run

# 本番実行
python main.py
```

## GitHub Actionsでの自動化

`.github/workflows/daily_post.yml` が毎日21:00 JSTに自動実行（`workflow_dispatch`で手動実行も可）。`public/videos/`と`logs/theme-history.json`をpushするため、ワークフローに`permissions: contents: write`が必要（設定済み）。

### 必要なGitHub Secrets

| Secret | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API（本日のテーマ生成用） |
| `GEMINI_API_KEY` | Google Gemini API（Nano Banana 2 / `gemini-3.1-flash-image`によるルックブック画像生成用） |
| `YOUTUBE_TOKEN_JSON` | ローカルで生成した`youtube_token.json`の中身をそのまま貼り付け |
| `YOUTUBE_CLIENT_SECRETS_JSON` | `client_secrets.json`の中身をそのまま貼り付け |
| `TIKTOK_ACCESS_TOKEN` / `TIKTOK_DOMAIN_VERIFIED` | 審査完了後（任意、現状コード未接続） |
| `INSTAGRAM_ACCESS_TOKEN` / `INSTAGRAM_BUSINESS_ACCOUNT_ID` | 審査完了後（任意、現状コード未接続） |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | 有料プラン契約後（任意、現状コード未接続） |
| `PINTEREST_CLIENT_ID` / `PINTEREST_CLIENT_SECRET` / `PINTEREST_REFRESH_TOKEN` | Pinterest API OAuth（参考ボード画像取得用、`pinterest_reference.py`単体でのみ使用） |
| `GH_PAT_SECRETS_WRITE` | Secrets書き込み権限を持つfine-grained PAT（Pinterestのrefresh_tokenローテーション書き戻し用） |

動画合成(`assemble_video.py`)はffmpeg(GitHub Actions runnerにapt-getでインストール)で行うため外部APIキー不要。Creatomateは最安プランが月$54で予算超過のため不採用（旧`creatomate_render.py`はKling時代の未使用コードとして残置）。

## ファイル構成

```
video-pipeline/
├── main.py                    # 日次パイプラインのオーケストレーター
├── theme_gen.py                # Claudeで本日のテーマ+7ルック分の服装差分を生成
├── generate_looks.py           # Gemini API(Nano Banana 2)でベース+7ルック画像を生成
├── assemble_video.py           # Pillow+ffmpegで7ルック画像を1本の9:16動画に合成
├── retry_utils.py             # 一時的なネットワークエラーのリトライ共通処理
├── youtube_upload.py          # YouTube Shorts アップロード
├── tiktok_upload.py            # TikTok Content Posting API（未接続、審査完了後接続予定）
├── instagram_upload.py         # Instagram Graph API（未接続、審査完了後接続予定）
├── x_upload.py                 # X API v2（未接続、有料プラン契約後接続予定）
├── pinterest_reference.py     # Pinterest非公開ボードから参考画像URLを取得（単体検証済み、本体未接続）
├── prompt_gen.py               # (Kling時代の旧実装、未使用)
├── creatomate_render.py        # (Kling時代の旧実装、未使用)
├── config.py                   # (Kling時代の旧実装、未使用。現行モジュールは各自ローカルにenvを読む設計)
├── requirements.txt
├── .env.example
├── assets/bgm/chill-lofi.mp3   # BGM(Pixabay Content License、商用可・帰属表示不要)
├── public/videos/               # 日次生成された動画（投稿用に一時公開、日次cronがpush）
├── logs/theme-history.json      # 直近のテーマ履歴（重複回避用、日次cronがpush）
├── prompts/look_crewneck_knit.md  # 初期検証用の固定テーマ資料（参考、本体では動的生成に移行済み）
├── .github/workflows/daily_post.yml            # 日次cron本体
├── .github/workflows/test-pinterest-fetch.yml  # Pinterest取得の動作検証用（workflow_dispatchのみ）
├── .github/workflows/test-generate-looks.yml   # ルックブック画像生成の動作検証用（workflow_dispatchのみ）
├── .github/workflows/test-assemble-video.yml   # ffmpeg動画合成の動作検証用（workflow_dispatchのみ）
└── api-applications/            # Instagram / TikTok API 申請資料
    ├── privacy-policy.md
    ├── tiktok-checklist.md
    └── instagram-checklist.md
```
