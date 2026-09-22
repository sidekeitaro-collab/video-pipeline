# TikTok Content Posting API — 申請チェックリスト

申請URL: https://developers.tiktok.com/products/content-posting-api/

## 必須提出物

- [ ] **プライバシーポリシーURL** → `privacy-policy.md` をホスティングする (GitHub Pages 等)
- [ ] **デモ動画** (最重要) — 以下を1本の動画で撮影:
  - OAuth認証フロー (TikTokログイン画面 → 許可)
  - 動画選択・プレビュー表示
  - 投稿実行 → TikTok上での確認
- [ ] **データ取り扱い説明文** (英語):

```
This application automates video publishing to TikTok on behalf of the account owner.
It uses the Content Posting API to upload AI-generated short videos.
OAuth tokens are stored locally and never transmitted to third parties.
No user data beyond what is required for the posting workflow is collected.
```

## UX要件 (実装必須)

- [ ] 投稿前にコンテンツプレビューを表示する
- [ ] ユーザーの明示的な同意後に投稿開始する
- [ ] duet / stitch / コメント設定をユーザーが変更できる
- [ ] ブランドコンテンツ開示オプションを提供する (デフォルトOFF)
- [ ] ロゴ・透かし・宣伝文を動画に重畳しない

## 審査期間

- [推計] 2〜6週間
- 未審査中: `SELF_ONLY` (非公開) 投稿のみ可能

## 投稿制限

- 1アカウント / 24時間: 最大15投稿

## 次のアクション

1. `privacy-policy.md` をGitHub Pagesでホスティング
2. デモ動画撮影 (dry-runモードで画面録画)
3. https://developers.tiktok.com/apps/ でアプリ登録 → Content Posting API 申請
