#!/usr/bin/env python3
"""
ffmpegで7ルック画像を1本の9:16縦型動画に組み立てる(Creatomate不使用、外部APIコストゼロ)。

各画像にPillowでテキストオーバーレイ(商品名+LOOK表記)を焼き込んだ上で、ffmpegのconcat
demuxerで0.9秒ずつハードカットで連結する。BGMは任意(未設定なら無音の動画のみ出力)。

ffmpegと日本語フォントは`apt-get install -y ffmpeg fonts-noto-cjk`で導入する前提
(ワークフロー側で実施。ubuntu-latestランナーにffmpegは標準搭載されていない)。

動作検証用(test-assemble-video.yml)からのみ実行する想定。
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(REPO_ROOT, "generated", "crewneck_knit")

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
IMAGE_DURATION = 0.9  # 秒/ルック、ハードカット(トランジションなし)

# GitHub Actions(ubuntu-latest)で `apt-get install -y fonts-noto-cjk` 後に存在するパス。
# ローカル(macOS)で検証する場合はヒラギノ角ゴ等、存在するCJK対応フォントを指定すること。
FONT_PATH_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

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


def _resolve_font_path() -> str:
    for path in FONT_PATH_CANDIDATES:
        if os.path.exists(path):
            return path
    raise RuntimeError(
        "日本語対応フォントが見つかりません。GitHub Actions上では"
        "`apt-get install -y fonts-noto-cjk`を先に実行してください。"
        f"(探索したパス: {FONT_PATH_CANDIDATES})"
    )


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def render_look_with_text(
    image_path: str, product_name: str, look_tag: str, font_path: str, output_path: str
) -> None:
    """画像を9:16キャンバスにcover配置し、下部中央にテキスト(白文字+影)を焼き込む。"""
    img = Image.open(image_path).convert("RGB")

    # cover配置: 9:16キャンバスを埋めるようリサイズ+中央クロップ
    canvas_ratio = OUTPUT_WIDTH / OUTPUT_HEIGHT
    img_ratio = img.width / img.height
    if img_ratio > canvas_ratio:
        new_height = OUTPUT_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        new_width = OUTPUT_WIDTH
        new_height = int(new_width / img_ratio)
    img = img.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - OUTPUT_WIDTH) // 2
    top = (new_height - OUTPUT_HEIGHT) // 2
    img = img.crop((left, top, left + OUTPUT_WIDTH, top + OUTPUT_HEIGHT))

    draw = ImageDraw.Draw(img)
    font_main = ImageFont.truetype(font_path, size=int(OUTPUT_HEIGHT * 0.038))
    font_tag = ImageFont.truetype(font_path, size=int(OUTPUT_HEIGHT * 0.030))

    def draw_centered_with_shadow(text: str, y: int, font: ImageFont.FreeTypeFont) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (OUTPUT_WIDTH - text_w) // 2
        shadow_offset = max(1, int(OUTPUT_HEIGHT * 0.0015))
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), text, font=font, fill=(255, 255, 255))

    base_y = int(OUTPUT_HEIGHT * 0.86)
    draw_centered_with_shadow(product_name, base_y, font_main)
    draw_centered_with_shadow(look_tag, base_y + int(OUTPUT_HEIGHT * 0.045), font_tag)

    img.save(output_path)


def build_video(look_frame_paths: list[str], bgm_path: str | None, output_path: str) -> str:
    """concat demuxerで画像を連結し、任意でBGMを合成してmp4を出力する。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        concat_list_path = os.path.join(tmpdir, "concat_list.txt")
        with open(concat_list_path, "w") as f:
            for frame_path in look_frame_paths:
                f.write(f"file '{frame_path}'\nduration {IMAGE_DURATION}\n")
            # concat demuxerの仕様上、最後のdurationは無視されるため最終フレームをもう一度書く
            f.write(f"file '{look_frame_paths[-1]}'\n")

        total_duration = round(len(look_frame_paths) * IMAGE_DURATION, 3)
        video_args = ["-f", "concat", "-safe", "0", "-i", concat_list_path]

        if bgm_path:
            video_args += [
                "-i", bgm_path,
                "-filter:a", "volume=0.7",
                "-t", str(total_duration),
                "-c:a", "aac",
                "-shortest",
            ]

        video_args += [
            # IMAGE_DURATION(0.9秒)はデフォルトの25fpsだと22.5フレームという非整数値になり、
            # concat demuxerの各セグメント境界でフレームがずれる(実機検証で確認済み: 全ルックが
            # 1つ後ろにずれて表示される)。30fpsなら0.9秒=27.0フレームと割り切れるため明示指定する。
            "-r", "30",
            # concat demuxerの「最終行を duration 無しでもう一度書く」お作法(最後のdurationが
            # 無視される仕様への対処)と-rの組み合わせで、末尾が想定より長く伸びる場合がある
            # (実機検証で確認済み)。-tで合計尺を明示的に打ち切ることで安全側に倒す。
            "-t", str(total_duration),
            "-vf", f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        _run_ffmpeg(video_args)

    print(f"[ffmpeg] Saved: {output_path}")
    return output_path


def main() -> None:
    font_path = _resolve_font_path()

    with tempfile.TemporaryDirectory() as tmpdir:
        frame_paths = []
        for i, (product_name, look_tag) in enumerate(LOOK_LABELS, start=1):
            src = os.path.join(IMAGES_DIR, f"look_{i:02d}.png")
            dst = os.path.join(tmpdir, f"frame_{i:02d}.png")
            render_look_with_text(src, product_name, look_tag, font_path, dst)
            frame_paths.append(dst)
            print(f"[Pillow] Rendered text overlay: look {i}/{len(LOOK_LABELS)}")

        # BGMのパスはここ1箇所にまとめる。未設定(None)なら無音の動画を出力する。
        # Pixabay Content License(商用可・帰属表示不要)下で入手した"Chill Lofi" by ZephiraMusic。
        bgm_path = os.path.join(REPO_ROOT, "assets", "bgm", "chill-lofi.mp3")

        build_video(frame_paths, bgm_path, os.path.join(REPO_ROOT, "output", "assembled_video.mp4"))


if __name__ == "__main__":
    main()
