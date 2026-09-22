import json
import re
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an expert scriptwriter for short-form vertical videos (9:16, 30-60s) for TikTok/YouTube Shorts/Instagram Reels/X.

Output JSON only, no explanation, matching this exact schema:
{
  "title": "engaging title under 60 chars",
  "script": "narration script in natural spoken Japanese, 30-60 seconds when read aloud, hook in first 3 seconds",
  "background_query": "2-4 English keywords describing an abstract/b-roll background video to search stock footage for (e.g. 'ocean waves aerial')",
  "description": "2-3 sentence description with hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}

Rules:
- script is the full narration text passed to text-to-speech, written in Japanese
- background_query must be generic b-roll footage that pairs with the topic visually, not literal illustration of the script
- Target: cinematic, eye-catching, social media optimized"""

REQUIRED_KEYS = ("title", "script", "background_query", "description", "tags")


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

    raise ValueError(f"ClaudeのレスポンスからJSONを抽出できませんでした:\n{text}")


def generate_video_content(topic: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Create a short video script for: {topic}"}],
    )
    text = response.content[0].text
    content = _extract_json(text)

    missing = [k for k in REQUIRED_KEYS if k not in content]
    if missing:
        raise ValueError(f"Claudeの出力に必須キーが不足しています: {missing}\n受信内容: {content}")

    return content
