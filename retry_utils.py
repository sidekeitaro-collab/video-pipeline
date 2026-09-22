import time
import requests


def request_with_retry(method: str, url: str, retries: int = 3, backoff: int = 3, **kwargs) -> requests.Response:
    """一時的なネットワークエラー(タイムアウト/接続断/5xx)のみリトライする。4xxは即座に送出。"""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            if resp.status_code >= 500:
                resp.raise_for_status()
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as exc:
            last_exc = exc
            if attempt == retries:
                break
            print(f"  [retry] {method} {url} failed ({exc}), attempt {attempt}/{retries}...")
            time.sleep(backoff * attempt)
    raise last_exc
