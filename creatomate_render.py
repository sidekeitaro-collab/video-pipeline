import time
from retry_utils import request_with_retry
from config import (
    CREATOMATE_API_KEY,
    CREATOMATE_API_BASE,
    CREATOMATE_TEMPLATE_ID,
    ELEVENLABS_VOICE_ID,
    PEXELS_API_KEY,
    PEXELS_API_BASE,
)


def _creatomate_headers() -> dict:
    return {
        "Authorization": f"Bearer {CREATOMATE_API_KEY}",
        "Content-Type": "application/json",
    }


def fetch_background_video(query: str) -> str:
    """Pexelsで縦型のb-roll素材を検索し、mp4のURLを1本返す。上位候補にmp4がなければ次点を試す。"""
    resp = request_with_retry(
        "GET",
        f"{PEXELS_API_BASE}/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 5},
        timeout=15,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        raise RuntimeError(f"Pexelsで背景素材が見つかりませんでした: '{query}'")

    for video in videos:
        video_files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"]
        if video_files:
            best = max(video_files, key=lambda f: f.get("height", 0))
            print(f"[Pexels] Background: {best['link']}")
            return best["link"]

    raise RuntimeError(f"Pexelsの検索結果{len(videos)}件すべてにmp4ファイルがありませんでした: '{query}'")


def create_render(title: str, script: str, background_url: str) -> str:
    payload = {
        "template_id": CREATOMATE_TEMPLATE_ID,
        "modifications": {
            "Title": title,
            # Creatomateのaudio要素がElevenLabsを直接呼び出す(providerを template側で設定済み前提)。
            # ここでは台本テキストとVoice IDのみ差し替える。
            "Voiceover-1.source": script,
            "Voiceover-1.provider": f"elevenlabs voice_id={ELEVENLABS_VOICE_ID} model_id=eleven_multilingual_v2",
            "Background": background_url,
        },
    }
    resp = request_with_retry(
        "POST", f"{CREATOMATE_API_BASE}/renders", headers=_creatomate_headers(), json=payload, timeout=30
    )
    resp.raise_for_status()
    body = resp.json()

    # ドキュメント上template_idレンダーは配列を返す想定だが、単一オブジェクトで返る可能性もあるため両対応
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


def download_video(url: str, output_path: str) -> str:
    resp = request_with_retry("GET", url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"[Creatomate] Downloaded: {output_path}")
    return output_path
