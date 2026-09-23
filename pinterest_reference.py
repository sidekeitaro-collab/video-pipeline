#!/usr/bin/env python3
"""
Pinterestの非公開ボードからピン画像URLを取得する。

動作検証用(test-pinterest-fetch.yml)からのみ実行する想定で、日次cron本体
(daily_post.yml)には組み込まない。Pinterest v5のrefresh_tokenは使用の都度
ローテーションされる仕様のため、取得のたびに新しいrefresh_tokenをGitHub
Secretsへ書き戻す。
"""
import base64
import os

from nacl import encoding, public

from retry_utils import request_with_retry

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
GITHUB_API_BASE = "https://api.github.com"
SECRETS_REPO = "sidekeitaro-collab/video-pipeline"
SECRET_NAME = "PINTEREST_REFRESH_TOKEN"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"必須の環境変数 '{name}' が設定されていません。GitHub Secretsを確認してください。"
        )
    return value


def refresh_access_token() -> tuple[str, str]:
    """PinterestのOAuthトークンをリフレッシュする。(access_token, 新しいrefresh_token) を返す。"""
    client_id = _require_env("PINTEREST_CLIENT_ID")
    client_secret = _require_env("PINTEREST_CLIENT_SECRET")
    refresh_token = _require_env("PINTEREST_REFRESH_TOKEN")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = request_with_retry(
        "POST",
        f"{PINTEREST_API_BASE}/oauth/token",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()

    access_token = body.get("access_token")
    new_refresh_token = body.get("refresh_token")
    if not access_token or not new_refresh_token:
        raise RuntimeError("Pinterestのトークンレスポンスに access_token / refresh_token が含まれていません。")

    print("[Pinterest] Access token refreshed.")
    return access_token, new_refresh_token


def update_refresh_token_secret(new_refresh_token: str) -> None:
    """GitHub Actions Secretsの PINTEREST_REFRESH_TOKEN を新しい値に書き戻す。

    ここで例外を握りつぶさないこと。書き戻しに失敗したまま古いrefresh_tokenで
    処理を続けると、そのrefresh_tokenは既に使い捨てられているため次回以降の
    実行が全て失敗する。
    """
    pat = _require_env("GH_PAT_SECRETS_WRITE")
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    key_resp = request_with_retry(
        "GET",
        f"{GITHUB_API_BASE}/repos/{SECRETS_REPO}/actions/secrets/public-key",
        headers=headers,
        timeout=15,
    )
    key_resp.raise_for_status()
    key_body = key_resp.json()

    public_key = public.PublicKey(key_body["key"], encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(new_refresh_token.encode("utf-8"))
    encrypted_value = base64.b64encode(encrypted).decode("utf-8")

    put_resp = request_with_retry(
        "PUT",
        f"{GITHUB_API_BASE}/repos/{SECRETS_REPO}/actions/secrets/{SECRET_NAME}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_body["key_id"]},
        timeout=15,
    )
    put_resp.raise_for_status()
    print(f"[GitHub] Secret '{SECRET_NAME}' updated.")


def get_board_id(access_token: str, board_name: str = "AI動画_参考_メンズニット") -> str:
    """ボード名からボードIDを取得する(ページネーション対応)。"""
    headers = {"Authorization": f"Bearer {access_token}"}
    found_names = []
    bookmark = None

    while True:
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        resp = request_with_retry(
            "GET", f"{PINTEREST_API_BASE}/boards", headers=headers, params=params, timeout=15
        )
        resp.raise_for_status()
        body = resp.json()

        for board in body.get("items", []):
            found_names.append(board.get("name"))
            if board.get("name") == board_name:
                print(f"[Pinterest] Board found: {board_name} ({board['id']})")
                return board["id"]

        bookmark = body.get("bookmark")
        if not bookmark:
            break

    raise RuntimeError(
        f"ボード '{board_name}' が見つかりませんでした。取得できたボード名: {found_names}"
    )


def fetch_board_pin_images(access_token: str, board_id: str) -> list[str]:
    """ボード内の全ピンから画像URLを取得する(ページネーション対応)。"""
    headers = {"Authorization": f"Bearer {access_token}"}
    image_urls = []
    bookmark = None

    while True:
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        resp = request_with_retry(
            "GET",
            f"{PINTEREST_API_BASE}/boards/{board_id}/pins",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()

        for pin in body.get("items", []):
            images = pin.get("media", {}).get("images", {})
            image = images.get("originals") or images.get("1200x")
            if image and image.get("url"):
                image_urls.append(image["url"])

        bookmark = body.get("bookmark")
        if not bookmark:
            break

    print(f"[Pinterest] Fetched {len(image_urls)} pin images.")
    return image_urls


def main() -> None:
    # GH_PAT_SECRETS_WRITEが無い状態でrefresh_access_token()を先に呼ぶと、Pinterestの
    # refresh_tokenが消費・失効した直後に書き戻し先が無くて失敗する(古いrefresh_tokenは
    # 既に無効化済みのため復旧不能)。トークンを消費する前に書き戻し先の設定だけ確認する。
    _require_env("GH_PAT_SECRETS_WRITE")

    access_token, new_refresh_token = refresh_access_token()
    update_refresh_token_secret(new_refresh_token)

    board_id = get_board_id(access_token)
    image_urls = fetch_board_pin_images(access_token, board_id)

    print(f"[Pinterest] Total images: {len(image_urls)}")
    for url in image_urls:
        print(f"  {url}")


if __name__ == "__main__":
    main()
