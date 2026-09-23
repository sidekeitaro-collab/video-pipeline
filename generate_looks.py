#!/usr/bin/env python3
"""
Google Gemini API (Nano Banana 2 / gemini-3.1-flash-image) で、キャラクター一貫性の
あるファッションルックブック画像を生成する。

prompts/look_crewneck_knit.md のベース参照画像プロンプトで架空モデルを1枚生成し、
そのベース画像を参照(image input)として渡すことで顔・体型・背景・ポーズを固定したまま
服の記述だけを差し替えた7ルックを生成する。

動作検証用(test-generate-looks.yml)からのみ実行する想定。
"""
import base64
import os

from google import genai

MODEL_ID = "gemini-3.1-flash-image"
OUTPUT_DIR = "./output"

BASE_CHARACTER_PROMPT = (
    "fashion lookbook photo of a fictional young Japanese male model, early 20s, "
    "175cm slim-athletic build, short black neat hair, soft natural facial features, "
    "standing facing slightly left, hands relaxed at sides, calm neutral expression, "
    "full body shot head to shoe, soft anime-influenced illustration style but "
    "realistic skin/fabric texture, solid light blue background (#C5E1F5), "
    "soft studio lighting, subtle soft shadow under feet, no text, no watermark, "
    "no logo, vertical portrait composition --ar 9:16"
)

LOOK_PROMPTS = [
    # LOOK 01 — ネイビー×ベージュ
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing a navy crew-neck knit sweater, beige wide-leg trousers, "
    "white low-top sneakers, no text, no watermark, no logo --ar 9:16",
    # LOOK 02 — グレー×ブラック
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing a heather gray crew-neck knit sweater, black tapered slacks, "
    "black leather loafers, no text, no watermark, no logo --ar 9:16",
    # LOOK 03 — オフホワイト×シャツ襟出し
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing an off-white crew-neck knit sweater layered over a light blue "
    "collared shirt (collar visible), khaki chino pants, brown leather boots, "
    "no text, no watermark, no logo --ar 9:16",
    # LOOK 04 — マスタード×デニム
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing a mustard yellow crew-neck knit sweater, black straight denim jeans, "
    "white canvas sneakers, no text, no watermark, no logo --ar 9:16",
    # LOOK 05 — ブラック×キャップ
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing a black crew-neck knit sweater, gray jogger pants, black cap, "
    "black chunky sneakers, no text, no watermark, no logo --ar 9:16",
    # LOOK 06 — ボルドー×眼鏡
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing a burgundy crew-neck knit sweater, beige chino pants, round "
    "tortoiseshell glasses, brown loafers, no text, no watermark, no logo --ar 9:16",
    # LOOK 07 — グリーン×マフラー
    "same model, same face, same pose, same light blue background (#C5E1F5), "
    "wearing an olive green crew-neck knit sweater, black wide-leg trousers, "
    "a cream knit scarf draped loosely, black ankle boots, no text, no watermark, "
    "no logo --ar 9:16",
]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"必須の環境変数 '{name}' が設定されていません。GitHub Secretsを確認してください。"
        )
    return value


def generate_base_character(api_key: str) -> bytes:
    """ベース参照画像(架空モデルのキャラクター固定用)を1枚生成する。"""
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(model=MODEL_ID, input=BASE_CHARACTER_PROMPT)
    return base64.b64decode(interaction.output_image.data)


def generate_look_variant(api_key: str, base_image_bytes: bytes, look_prompt: str) -> bytes:
    """ベース画像を参照として渡し、服の記述だけを差し替えた1ルックを生成する。"""
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=MODEL_ID,
        input=[
            {"type": "text", "text": look_prompt},
            {
                "type": "image",
                "data": base64.b64encode(base_image_bytes).decode("utf-8"),
                "mime_type": "image/png",
            },
        ],
    )
    return base64.b64decode(interaction.output_image.data)


def save_image(image_bytes: bytes, path: str) -> None:
    with open(path, "wb") as f:
        f.write(image_bytes)
    print(f"[Gemini] Saved: {path}")


def main() -> None:
    api_key = _require_env("GEMINI_API_KEY")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[Gemini] Generating base character image (model: {MODEL_ID})...")
    base_image_bytes = generate_base_character(api_key)
    save_image(base_image_bytes, os.path.join(OUTPUT_DIR, "base.png"))

    total = len(LOOK_PROMPTS)
    success_count = 0
    failed_looks = []

    for i, look_prompt in enumerate(LOOK_PROMPTS, start=1):
        print(f"[Gemini] Generating look {i}/{total}...")
        try:
            look_bytes = generate_look_variant(api_key, base_image_bytes, look_prompt)
            save_image(look_bytes, os.path.join(OUTPUT_DIR, f"look_{i:02d}.png"))
            success_count += 1
        except Exception as exc:
            # 1ルックの失敗で他のルック生成を止めない(全体はベスト・エフォートで進める)
            print(f"[Gemini] ERROR: look {i:02d} の生成に失敗しました: {exc}")
            failed_looks.append(i)

    print(f"[Gemini] 完了: 成功 {success_count}/{total} 枚, 失敗 {len(failed_looks)}/{total} 枚")
    if failed_looks:
        print(f"[Gemini] 失敗したlook番号: {failed_looks}")


if __name__ == "__main__":
    main()
