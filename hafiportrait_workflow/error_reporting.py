from __future__ import annotations

from typing import Literal


UploadFailCategory = Literal[
    "auth_error",
    "rate_limited",
    "server_error",
    "client_error",
    "timeout",
    "network_error",
    "unexpected_response",
    "unknown",
]


def extract_status_code(err: str) -> int | None:
    # Common format: "HTTP 403: ..." or "HTTP 403"
    s = (err or "").strip()
    if not s.startswith("HTTP "):
        return None
    parts = s.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1].rstrip(":"))
    except Exception:
        return None


def classify_upload_failure(status_code: int | None, err: str) -> UploadFailCategory:
    if status_code in (401, 403):
        return "auth_error"
    if status_code == 429:
        return "rate_limited"
    if status_code in (500, 502, 503, 504):
        return "server_error"
    if status_code is not None and 400 <= status_code < 500:
        return "client_error"

    low = (err or "").lower()
    if "unexpected_response" in low:
        return "unexpected_response"
    if "timeout" in low:
        return "timeout"
    if "connection" in low or "network" in low:
        return "network_error"

    return "unknown"
