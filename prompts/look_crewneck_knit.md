# テーマ: クルーネックニット (2026-09 秋バッチ)

主役アイテム1つ(クルーネックニット)を、色/インナー/ボトムス/小物で7パターンに展開する。LOOKS NOTE(@looksnote11)風 — 全身ショット・イラスト調だが質感はリアル寄り・単色背景のファッションルックブック。

## 生成方式(Flux Kontext / Nano Banana 2 共通の運用)

1. まず「ベース参照画像」を1枚だけ生成する(下記キャラクター固定プロンプト)。
2. 以降の7ルックは、そのベース画像を参照(image reference / img2img)として渡し、**顔・体型・背景・ポーズの骨格は固定したまま服の記述だけ差し替える**。
3. テキスト(商品名/LOOK01等)は画像に焼き込まない — Creatomate側でオーバーレイするため、プロンプトには "no text, no watermark, no logo" を必ず入れる。
4. キャラクターは完全架空の人物として設計する(実在の人物の肖像を参照・模倣しない)。年齢・体格・髪型はやや曖昧目にして特定の実在人物に似すぎないようにする。

## ベース参照画像プロンプト(キャラクター固定用)

```
fashion lookbook photo of a fictional young Japanese male model, early 20s,
175cm slim-athletic build, short black neat hair, soft natural facial features,
standing facing slightly left, hands relaxed at sides, calm neutral expression,
full body shot head to shoe, soft anime-influenced illustration style but
realistic skin/fabric texture, solid light blue background (#C5E1F5),
soft studio lighting, subtle soft shadow under feet, no text, no watermark,
no logo, vertical portrait composition --ar 9:16
```

## 7ルック差分プロンプト(ベース画像を参照して服だけ差し替え)

各プロンプトの先頭 `same model, same face, same pose, same light blue background (#C5E1F5)` は共通— キャラ固定を毎回明示する。

**LOOK 01 — ネイビー×ベージュ**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing a navy crew-neck knit sweater, beige wide-leg trousers,
white low-top sneakers, no text, no watermark, no logo --ar 9:16
```

**LOOK 02 — グレー×ブラック**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing a heather gray crew-neck knit sweater, black tapered slacks,
black leather loafers, no text, no watermark, no logo --ar 9:16
```

**LOOK 03 — オフホワイト×シャツ襟出し**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing an off-white crew-neck knit sweater layered over a light blue
collared shirt (collar visible), khaki chino pants, brown leather boots,
no text, no watermark, no logo --ar 9:16
```

**LOOK 04 — マスタード×デニム**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing a mustard yellow crew-neck knit sweater, black straight denim jeans,
white canvas sneakers, no text, no watermark, no logo --ar 9:16
```

**LOOK 05 — ブラック×キャップ**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing a black crew-neck knit sweater, gray jogger pants, black cap,
black chunky sneakers, no text, no watermark, no logo --ar 9:16
```

**LOOK 06 — ボルドー×眼鏡**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing a burgundy crew-neck knit sweater, beige chino pants, round
tortoiseshell glasses, brown loafers, no text, no watermark, no logo --ar 9:16
```

**LOOK 07 — グリーン×マフラー**
```
same model, same face, same pose, same light blue background (#C5E1F5),
wearing an olive green crew-neck knit sweater, black wide-leg trousers,
a cream knit scarf draped loosely, black ankle boots, no text, no watermark,
no logo --ar 9:16
```

## 動画組み立て側で使うテキスト(Creatomateオーバーレイ用、参考)

| # | 商品名(日本語) | LOOK表記 |
|---|---|---|
| 1 | ネイビークルーネックニット | LOOK 01 |
| 2 | グレークルーネックニット | LOOK 02 |
| 3 | オフホワイトクルーネックニット | LOOK 03 |
| 4 | マスタードクルーネックニット | LOOK 04 |
| 5 | ブラッククルーネックニット | LOOK 05 |
| 6 | ボルドークルーネックニット | LOOK 06 |
| 7 | グリーンクルーネックニット | LOOK 07 |

## 未決定事項

- 画像生成ツールの最終選定(Flux Kontext vs Nano Banana 2、または併用)は未確定。
- Pinterestボード「AI動画_参考_メンズニット」の参考画像を実際にどう生成プロンプトへ反映するか(参照画像として直接渡すのか、構図だけ言語化して転記するのか)は未設計。
