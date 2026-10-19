"""Tiny stdlib HTTP helper with retry/backoff. No third-party deps."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

UA = "ai-job-search-autopilot/1.0 (personal job search; low volume)"


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.body = body


def request(url: str, *, method: str = "GET", data: bytes | None = None,
            headers: dict | None = None, timeout: float = 30, retries: int = 3) -> tuple[int, bytes, str]:
    """Return (status, body, final_url). Retries 429/5xx and network errors."""
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), resp.geturl()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:2000]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt * 2)
                last = HttpError(e.code, url, body)
                continue
            raise HttpError(e.code, url, body) from None
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
    raise last if last else RuntimeError(f"request failed: {url}")


def get_json(url: str, **kw):
    _, body, _ = request(url, **kw)
    return json.loads(body.decode("utf-8"))


def post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 120):
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    _, body, _ = request(url, method="POST", data=json.dumps(payload).encode(), headers=hdrs, timeout=timeout)
    return json.loads(body.decode("utf-8"))
