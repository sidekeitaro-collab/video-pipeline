#!/usr/bin/env python3
"""
Creatomateの RenderScript (JSON) を使って、7ルック画像を1本の9:16縦型動画に組み立てる。

Web UIのテンプレート機能は使わず、動画構成を丸ごとJSONで組み立ててAPIに直接渡す方式
(creatomate.com/docs/api/render-script/json-structure)。Kling時代のcreatomate_render.py
(template_id + ElevenLabsナレーション前提)とは独立した新規実装。config.pyはこのフローで
不要な環境変数(ELEVENLABS_VOICE_ID等)を無条件でrequireする設計のためimportしない。

動作検証用(test-assemble-video.yml)からのみ実行する想定。
"""
import os
import time

from retry_utils import request_with_retry

CREATOMATE_API_BASE = "https://api.creatomate.com/v2"
REPO_RAW_BASE = (
    "https://raw.githubusercontent.com/sidekeitaro-collab/video-pipeline/main/generated/crewneck_knit"
)

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
IMAGE_DURATION = 0.9  # 秒/ルック、ハードカット(トランジションなし)

# prompts/look_crewneck_knit.md の「動画組み立て側で使うテキスト」表に対応
LOOK_LABELS = [
    ("ネイビークルーネックニット", "LOOK 01"),
    ("グレークルーネックニット", "LOOK 02"),
    ("オフホワイトクルーネックニット", "LOOK 03"),
    ("マスタードクルーネックニット", "LOOK 04"),
    ("ブラッククルーネックニット", "LOOK 05"),
    ("ボルドークルーネックニット", "LOOK 06"),
    ("グリーンクルーネックニット", "LOOK 07"),
]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"必須の環境変数 '{name}' が設定されていません。.env またはGitHub Secretsを確認してください。"
        )
    return value


def _creatomate_headers() -> dict:
    return {
        "Authorization": f"Bearer {_require_env('CREATOMATE_API_KEY')}",
        "Content-Type": "application/json",
    }


def build_render_script(
    look_urls: list[str], labels: list[tuple[str, str]], bgm_url: str | None
) -> dict:
    """7枚のlook画像+テキストオーバーレイ(+任意でBGM)を並べたRenderScript JSONを組み立てる。

    画像はtrack 1、テキストはtrack 2(track番号が大きいほど手前に描画される)に配置し、
    各要素のtime/durationを明示することでハードカットのタイミングを厳密に揃える。
    """
    if len(look_urls) != len(labels):
        raise ValueError(f"look_urls({len(look_urls)})とlabels({len(labels)})の件数が一致しません。")

    elements = []
    for i, (image_url, (product_name, look_tag)) in enumerate(zip(look_urls, labels)):
        start = round(i * IMAGE_DURATION, 3)

        elements.append(
            {
                "type": "image",
                "track": 1,
                "time": start,
                "duration": IMAGE_DURATION,
                "source": image_url,
                "fit": "cover",
                "width": "100%",
                "height": "100%",
            }
        )
        elements.append(
            {
                "type": "text",
                "track": 2,
                "time": start,
                "duration": IMAGE_DURATION,
                "text": f"{product_name}\n{look_tag}",
                "font_family": "Noto Sans JP",
                "font_weight": 500,
                "font_size": "5.5vmin",
                "fill_color": "#ffffff",
                "width": "90%",
                "x_alignment": "50%",
                "y_alignment": "100%",
                "y": "88%",
                "shadow_color": "rgba(0,0,0,0.6)",
                "shadow_blur": "1vmin",
                "shadow_x": "0.2vmin",
                "shadow_y": "0.2vmin",
            }
        )

    total_duration = round(len(look_urls) * IMAGE_DURATION, 3)

    if bgm_url:
        elements.append(
            {
                "type": "audio",
                "track": 3,
                "time": 0,
                "source": bgm_url,
                "duration": total_duration,
                "trim_start": 0,
                "trim_duration": total_duration,
                "volume": "70%",
            }
        )

    return {
        "output_format": "mp4",
        "width": OUTPUT_WIDTH,
        "height": OUTPUT_HEIGHT,
        "duration": total_duration,
        "elements": elements,
    }


def create_render(render_script: dict) -> str:
    resp = request_with_retry(
        "POST", f"{CREATOMATE_API_BASE}/renders", headers=_creatomate_headers(), json=render_script, timeout=30
    )
    resp.raise_for_status()
    body = resp.json()

    # /v2/renders は単一リクエストでもレンダー配列(1件)を返す
    render = body[0] if isinstance(body, list) else body
    if "id" not in render:
        raise RuntimeError(f"Creatomateのレスポンス形式が想定と異なります: {body}")

    print(f"[Creatomate] Render created: {render['id']} (status: {render.get('status')})")
    return render["id"]


def wait_for_render(render_id: str, poll_interval: int = 5, timeout: int = 300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = request_with_retry(
            "GET", f"{CREATOMATE_API_BASE}/renders/{render_id}", headers=_creatomate_headers(), timeout=15
        )
        resp.raise_for_status()
        render = resp.json()
        status = render.get("status")
        print(f"[Creatomate] Status: {status}")

        if status == "succeeded":
            url = render.get("url")
            if not url:
                raise RuntimeError(f"Creatomateがsucceededを返しましたがurlがありません: {render}")
            return url
        elif status == "failed":
            raise RuntimeError(f"Creatomate render failed: {render.get('error_message')}")

        time.sleep(poll_interval)

    raise TimeoutError(f"Creatomate render {render_id} did not complete within {timeout}s")


def download_video(url: str, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    resp = request_with_retry("GET", url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"[Creatomate] Downloaded: {path}")
    return path


def main() -> None:
    look_urls = [f"{REPO_RAW_BASE}/look_{i:02d}.png" for i in range(1, 8)]

    # BGMのURLはここ1箇所にまとめる。著作権フリー音源の選定自体は別タスク。
    # 未設定(None)の場合は音声無しで動画を生成する(エラーにしない)。
    bgm_url = None

    render_script = build_render_script(look_urls, LOOK_LABELS, bgm_url)
    render_id = create_render(render_script)
    video_url = wait_for_render(render_id)
    download_video(video_url, "./output/assembled_video.mp4")


if __name__ == "__main__":
    main()
