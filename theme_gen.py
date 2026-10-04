#!/usr/bin/env python3
"""
Claude API で「本日のアイテムテーマ」+「本日のキャラクター外見」+ 7ルック分の
服装差分・ポーズ/表情差分を生成する。

画風(イラストタッチ)・背景色・構図・技術指定(--ar 9:16 等)は一貫性を保つため
コード側(generate_looks.py)の固定テンプレートに任せる。それ以外——アイテム・
キャラの外見(髪型/顔立ち/体格)・7ルックそれぞれの服装とポーズ/表情——は
Claudeに生成させ、キャラは同日の7ルック内では(image-to-imageの参照により)
自動的に一貫性が保たれる一方、日によって違う人物になるようにする。
"""
import json
import os
import re
from datetime import datetime

import anthropic

MODEL_ID = "claude-sonnet-5"
LOOK_COUNT = 7
HISTORY_LOOKBACK = 30

SYSTEM_PROMPT = f"""You are a fashion coordinator for a daily men's fashion lookbook video series.

Each day you:
1. Invent a NEW fictional male model's appearance (different from previous days — vary hair
   style/color, face shape, build, height, age range within 20s-30s).
2. Pick ONE item theme (a category of clothing, e.g. an oversized hoodie, a denim jacket).
3. Propose {LOOK_COUNT} distinct outfit variations built around it, each with a different
   color/pattern and different bottoms/accessories.
4. Give each of the {LOOK_COUNT} looks a distinct pose and facial expression, so the video
   doesn't feel static (e.g. hands in pockets with a slight smile, arms crossed looking
   confident, one hand adjusting the collar, looking over the shoulder, a relaxed stance
   with a neutral expression, etc).

Output JSON only, no explanation, matching this exact schema:
{{
  "item_theme": "today's item theme, in Japanese, e.g. 'オーバーサイズパーカー'",
  "character_description": "English description of the model's hair, face, and build only
    (NOT clothing, NOT pose, NOT expression, NOT background/art style), e.g. 'young Japanese
    male model, mid-20s, 178cm athletic build, short wavy brown hair, sharp jawline, calm eyes'",
  "looks": [
    {{
      "prompt_fragment": "English clothing description only, e.g. 'a navy oversized hoodie, black cargo pants, white sneakers'",
      "pose_fragment": "English pose and facial expression description only, e.g. 'standing
        with hands in pockets, slight confident smile, facing camera'",
      "product_name_ja": "Japanese product name for on-screen text, e.g. 'ネイビーオーバーサイズパーカー'"
    }},
    ... exactly {LOOK_COUNT} entries total
  ]
}}

Rules:
- character_description must NOT mention clothing, pose, expression, or the background. Those
  are handled separately.
- Do NOT include technical/rendering instructions (aspect ratio, "no text", "no watermark",
  art style, background color, etc) anywhere. Those are fixed elsewhere.
- prompt_fragment must be a short English clothing/accessory description only (what the model
  is wearing), suitable to be inserted directly after the word "wearing ".
- pose_fragment must NOT mention clothing, face shape/hair, or the background.
- Each of the {LOOK_COUNT} looks must have a visibly different color palette and/or bottoms/accessories,
  AND a visibly different pose/expression, from the others.
- product_name_ja must be a short, catchy Japanese product name suitable for an on-screen text overlay.
- Pick an item_theme not on the avoid-list below, if one is given."""

REQUIRED_LOOK_KEYS = ("prompt_fragment", "pose_fragment", "product_name_ja")


def _extract_json(text: str) -> dict:
    text = text.strip()
    # 直接パースできればそれで良い
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # ```json ... ``` / ``` ... ``` フェンスから抽出
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 最初の '{' から最後の '}' までを試す
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Claudeのレスポンスからテーマ用JSONを抽出できませんでした:\n{text}")


def _load_history(history_path: str) -> list[dict]:
    if not os.path.exists(history_path):
        return []
    with open(history_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


def _save_history(history_path: str, history: list[dict]) -> None:
    os.makedirs(os.path.dirname(history_path) or ".", exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _validate_theme(content: dict) -> None:
    if not str(content.get("item_theme", "")).strip():
        raise ValueError(f"Claudeの出力に item_theme がありません: {content}")

    if not str(content.get("character_description", "")).strip():
        raise ValueError(f"Claudeの出力に character_description がありません: {content}")

    looks = content.get("looks")
    if not isinstance(looks, list) or len(looks) != LOOK_COUNT:
        raise ValueError(
            f"Claudeの出力の looks は {LOOK_COUNT} 件の配列である必要があります: {content}"
        )

    for i, look in enumerate(looks):
        if not isinstance(look, dict):
            raise ValueError(f"Claudeの出力の looks[{i}] がオブジェクトではありません: {look}")
        missing = [k for k in REQUIRED_LOOK_KEYS if not str(look.get(k, "")).strip()]
        if missing:
            raise ValueError(
                f"Claudeの出力の looks[{i}] に必須キーが不足しています: {missing}\n受信内容: {look}"
            )


def generate_theme(api_key: str, history_path: str = "logs/theme-history.json", date_str: str | None = None) -> dict:
    """本日のテーマ(item_theme)と7ルック分の服装差分(looks)をClaudeに生成させる。

    直近 HISTORY_LOOKBACK 件の item_theme を避けるようプロンプトに含め、生成に
    成功したら history_path に新しい item_theme を追記して保存する。

    戻り値: {"item_theme": str, "character_description": str,
             "looks": [{"prompt_fragment": str, "pose_fragment": str, "product_name_ja": str}, ...]} (7要素)
    """
    history = _load_history(history_path)
    recent_themes = [h["item_theme"] for h in history[-HISTORY_LOOKBACK:] if h.get("item_theme")]

    user_prompt = "Propose today's item theme and 7 looks."
    if recent_themes:
        user_prompt += f"\n\n直近使用したテーマ: {recent_themes} は避けてください。"

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # claude-sonnet-5はデフォルトでThinkingBlockを含むことがあり、content[0]が
    # 必ずしもtextブロックとは限らない(実機検証で確認済み)。type=="text"のブロックを探す。
    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError(f"Claudeのレスポンスにtextブロックがありません: {response.content}")
    text = "".join(text_blocks)
    content = _extract_json(text)
    _validate_theme(content)

    history.append({
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "item_theme": content["item_theme"],
    })
    _save_history(history_path, history)

    return content
