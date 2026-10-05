#!/usr/bin/env python3
"""
Google Gemini API (Nano Banana 2 / gemini-3.1-flash-image) で、キャラクター一貫性の
あるファッションルックブック画像を生成する。

theme_gen.generate_theme()が返す本日のキャラクター外見(character_description)から
架空モデルのベース参照画像を1枚生成し、そのベース画像を参照(image input)として渡す
ことで顔・体型・背景を固定したまま、服とポーズ/表情をルックごとに差し替えた7枚を生成
する。画風(イラストタッチ)・背景色・構図はART_STYLE_TEMPLATEとしてコード側に固定し、
日によって変わらないようにする。

動作検証用(test-generate-looks.yml)からのみ実行する想定。
"""
import base64
import os

from google import genai

MODEL_ID = "gemini-3.1-flash-image"
OUTPUT_DIR = "./output"

# アスペクト比はプロンプト文字列の"--ar 9:16"ではなく、Interactions APIの
# response_formatパラメータで指定する仕様(公式ドキュメントで確認済み。未指定時の
# デフォルトは16:9で、9:16ではない)。image_sizeは画質と1枚あたりのコスト
# ($0.067@1K, $0.101@2K)のトレードオフ、2026-10-05にユーザー承認の上2Kへ変更。
# 既知リスク(Google AI Developer Forum報告): 2K/4Kはmulti-turn(画像参照あり)呼び出しで
# 404になる場合がある——generate_look_variant()はbase_image_bytesを参照として渡す
# multi-turn呼び出しのため、該当すればそこで顕在化する。dry-run実機検証で確認すること。
RESPONSE_FORMAT = {
    "type": "image",
    # response_format.mime_typeは'image/jpeg'のみ対応('image/png'は400エラー、
    # 実機検証で確認済み)。
    "mime_type": "image/jpeg",
    "aspect_ratio": "9:16",
    "image_size": "2K",
}

# 画風・構図・技術指定。日によって変えず、ここを編集すれば毎日同じ新タッチで統一
# される。現在はフラットなイラスト寄り(写実的な質感は避ける)。背景色は固定せず
# theme_gen.generate_theme()が返すbackground_colorを都度差し込む(日替わり)。
ART_STYLE_TEMPLATE = (
    "flat clean digital illustration style, crisp bold linework, cel-shaded with "
    "minimal flat color blocks, anime/manga-inspired, no photorealistic shading or "
    "texture, solid background color ({background_color}), soft even lighting, subtle "
    "flat shadow under feet, no text, no watermark, no logo, vertical portrait composition --ar 9:16"
)

DEFAULT_BACKGROUND_COLOR = "#C5E1F5"

BASE_CHARACTER_TEMPLATE = (
    "fashion lookbook photo of a fictional {character_description}, "
    "standing facing slightly left, hands relaxed at sides, calm neutral expression, "
    "full body shot head to shoe, {art_style}"
)

# ベース画像には服装の記述が一切無い(キャラ/背景/構図のみ)ため、アイテムテーマは
# ここではなく各ルックのプロンプト(LOOK_PROMPT_TEMPLATE)側にのみ差し込まれる。
# ポーズ/表情はルックごとに変える(「same pose」は固定しない)——顔の同一性は
# "same face"とベース画像参照(image-to-image)で担保する。背景色は同日の7ルック内
# では固定(1本の動画として統一感を保つため、ルックごとには変えない)。
LOOK_PROMPT_TEMPLATE = (
    "same model, same face, same background color ({background_color}), full body shot, "
    "{pose_fragment}, wearing {prompt_fragment}, no text, no watermark, no logo --ar 9:16"
)


def build_base_prompt(character_description: str, background_color: str = DEFAULT_BACKGROUND_COLOR) -> str:
    """theme_gen.generate_theme()のcharacter_description/background_colorを、画風/構図
    込みの完全なベース画像生成プロンプトに差し込む。"""
    art_style = ART_STYLE_TEMPLATE.format(background_color=background_color)
    return BASE_CHARACTER_TEMPLATE.format(
        character_description=character_description, art_style=art_style
    )


def build_look_prompt(
    prompt_fragment: str, pose_fragment: str, background_color: str = DEFAULT_BACKGROUND_COLOR
) -> str:
    """theme_gen.generate_theme()のlooks[i]["prompt_fragment"]/["pose_fragment"]と
    background_colorを、キャラ/背景/技術指定込みの完全なルック生成プロンプトに差し込む。"""
    return LOOK_PROMPT_TEMPLATE.format(
        prompt_fragment=prompt_fragment, pose_fragment=pose_fragment, background_color=background_color
    )


# main()単体実行(CLIでの動作確認)用の固定テーマ。
_TEST_CHARACTER_DESCRIPTION = (
    "young Japanese male model, early 20s, 175cm slim-athletic build, short black "
    "neat hair, soft natural facial features"
)

_TEST_LOOK_FRAGMENTS = [
    # LOOK 01 — ネイビー×ベージュ
    ("a navy crew-neck knit sweater, beige wide-leg trousers, white low-top sneakers",
     "standing with hands in pockets, slight smile, facing camera"),
    # LOOK 02 — グレー×ブラック
    ("a heather gray crew-neck knit sweater, black tapered slacks, black leather loafers",
     "arms crossed, confident expression, facing slightly left"),
    # LOOK 03 — オフホワイト×シャツ襟出し
    ("an off-white crew-neck knit sweater layered over a light blue collared shirt "
     "(collar visible), khaki chino pants, brown leather boots",
     "one hand adjusting the collar, looking over the shoulder"),
    # LOOK 04 — マスタード×デニム
    ("a mustard yellow crew-neck knit sweater, black straight denim jeans, white canvas sneakers",
     "relaxed stance, hands at sides, neutral expression, facing camera"),
    # LOOK 05 — ブラック×キャップ
    ("a black crew-neck knit sweater, gray jogger pants, black cap, black chunky sneakers",
     "one hand adjusting the cap, playful smile"),
    # LOOK 06 — ボルドー×眼鏡
    ("a burgundy crew-neck knit sweater, beige chino pants, round tortoiseshell glasses, "
     "brown loafers",
     "standing with one hand in pocket, chin slightly raised, confident look"),
    # LOOK 07 — グリーン×マフラー
    ("an olive green crew-neck knit sweater, black wide-leg trousers, a cream knit scarf "
     "draped loosely, black ankle boots",
     "slight walking pose, looking off to the side, calm expression"),
]

LOOK_PROMPTS = [
    build_look_prompt(fragment, pose) for fragment, pose in _TEST_LOOK_FRAGMENTS
]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"必須の環境変数 '{name}' が設定されていません。GitHub Secretsを確認してください。"
        )
    return value


def generate_base_character(api_key: str, base_prompt: str) -> bytes:
    """ベース参照画像(架空モデルのキャラクター固定用)を1枚生成する。"""
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=MODEL_ID,
        input=base_prompt,
        response_format=RESPONSE_FORMAT,
    )
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
                # 出力はRESPONSE_FORMATでimage/jpeg固定にしたため、参照として送り返す
                # base_image_bytesも実体はJPEG。
                "mime_type": "image/jpeg",
            },
        ],
        response_format=RESPONSE_FORMAT,
    )
    return base64.b64decode(interaction.output_image.data)


def save_image(image_bytes: bytes, path: str) -> None:
    with open(path, "wb") as f:
        f.write(image_bytes)
    print(f"[Gemini] Saved: {path}")


def generate_all_looks(api_key: str, theme: dict, output_dir: str) -> tuple[str, list[str]]:
    """theme_gen.generate_theme()が返すtheme dictから、ベース画像1枚+7ルック画像を
    生成しoutput_dirに保存する。(ベース画像パス, 7ルック画像パスのリスト) を返す。

    動画組み立て(assemble_video)にはルックが全て揃っている必要があるため、main()と
    異なり1ルックでも生成に失敗したら例外を送出する(ベスト・エフォートで進めない)。
    """
    os.makedirs(output_dir, exist_ok=True)

    background_color = theme.get("background_color", DEFAULT_BACKGROUND_COLOR)
    base_prompt = build_base_prompt(theme["character_description"], background_color)
    print(f"[Gemini] Generating base character image (model: {MODEL_ID}, bg: {background_color})...")
    base_image_bytes = generate_base_character(api_key, base_prompt)
    base_path = os.path.join(output_dir, "base.jpg")
    save_image(base_image_bytes, base_path)

    looks = theme["looks"]
    look_paths = []
    failed_looks = []

    for i, look in enumerate(looks, start=1):
        print(f"[Gemini] Generating look {i}/{len(looks)}: {look['product_name_ja']}...")
        look_prompt = build_look_prompt(look["prompt_fragment"], look["pose_fragment"], background_color)
        try:
            look_bytes = generate_look_variant(api_key, base_image_bytes, look_prompt)
            look_path = os.path.join(output_dir, f"look_{i:02d}.jpg")
            save_image(look_bytes, look_path)
            look_paths.append(look_path)
        except Exception as exc:
            print(f"[Gemini] ERROR: look {i:02d} の生成に失敗しました: {exc}")
            failed_looks.append(i)

    if failed_looks:
        raise RuntimeError(
            f"look画像の生成に失敗しました(look番号: {failed_looks})。"
            f"動画組み立てには{len(looks)}枚全てが必要です。"
        )

    return base_path, look_paths


def main() -> None:
    api_key = _require_env("GEMINI_API_KEY")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    base_prompt = build_base_prompt(_TEST_CHARACTER_DESCRIPTION)
    print(f"[Gemini] Generating base character image (model: {MODEL_ID})...")
    base_image_bytes = generate_base_character(api_key, base_prompt)
    save_image(base_image_bytes, os.path.join(OUTPUT_DIR, "base.jpg"))

    total = len(LOOK_PROMPTS)
    success_count = 0
    failed_looks = []

    for i, look_prompt in enumerate(LOOK_PROMPTS, start=1):
        print(f"[Gemini] Generating look {i}/{total}...")
        try:
            look_bytes = generate_look_variant(api_key, base_image_bytes, look_prompt)
            save_image(look_bytes, os.path.join(OUTPUT_DIR, f"look_{i:02d}.jpg"))
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
