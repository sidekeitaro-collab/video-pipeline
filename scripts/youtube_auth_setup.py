#!/usr/bin/env python3
"""
YouTube OAuthの初回認証専用の一回限りのローカルスクリプト。

main.py経由だとGemini/Claude APIキーがローカルに無いと先に進めないため、
これだけ切り出してyoutube_token.jsonを生成する。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youtube_upload import _get_credentials

if __name__ == "__main__":
    creds = _get_credentials()
    print("youtube_token.json を生成しました。")
