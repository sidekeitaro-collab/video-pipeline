# Instagram Graph API — 申請チェックリスト

申請URL: https://developers.facebook.com/apps/

## 前提条件 (先に準備)

- [ ] Instagramアカウントを **Businessアカウント** に切り替える
  - 設定 → アカウント → プロアカウントに切り替える → ビジネス
- [ ] **Facebookページ** を作成してInstagramアカウントに連携する
  - Meta Business Suite から連携可能

## Meta Developer App セットアップ

1. https://developers.facebook.com/apps/ → 新規アプリ作成
2. 用途: **ビジネス** を選択
3. Instagram Graph API 製品を追加

## 申請が必要なパーミッション

| パーミッション | 用途 | アクセスレベル |
|---|---|---|
| `instagram_business_basic` | アカウント情報取得 | Standard → Advanced |
| `instagram_business_content_publish` | Reels/動画投稿 | Standard → Advanced |

## 提出物 (パーミッションごとに必要)

- [ ] **スクリーンキャスト動画** (各パーミッションごと):
  - OAuthログイン → 許可 → 動画投稿 → Instagram上での確認
  - ユーザーフロー全体を録画
- [ ] **ユースケース説明** (英語):

```
This app automatically publishes AI-generated short-form videos (Reels) 
to Instagram Business accounts. The workflow: Claude AI generates the script,
ElevenLabs/Creatomate render the narrated video, and this app uploads via the
Content Publishing API. All actions are performed on accounts owned by the
operator. No third-party user data is collected or stored.
```

- [ ] **プライバシーポリシーURL**

## 技術要件

- [ ] 動画: **5〜90秒 / 9:16 縦型** (これ以外はReelsタブに表示されない)
- [ ] 投稿上限: 100投稿 / 24時間 (全コンテンツタイプ合計)

## Advanced Access 申請 (自分以外のアカウントに投稿する場合)

- [ ] 詳細なユースケース説明
- [ ] データ取り扱いポリシー
- [ ] プライバシーポリシー

## 審査期間

- [推計] 2〜4週間

## 次のアクション

1. Instagramアカウントをビジネスに切り替え
2. Facebookページ作成・連携
3. Meta for Developers でアプリ登録
4. スクリーンキャスト撮影 → 申請
