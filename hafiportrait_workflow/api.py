from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import time

import requests

from .constants import JPG_EXTS
from .logging_utils import get_logger, log_warning
from .models import Config


@dataclass(frozen=True, slots=True)
class UploadAttemptResult:
    ok: bool
    error: str
    status_code: int | None


@dataclass(slots=True)
class HafiportraitClient:
    api_base_url: str
    api_key: str
    timeout_seconds: int
    session: requests.Session

    @classmethod
    def from_config(cls, cfg: Config) -> "HafiportraitClient":
        sess = requests.Session()
        sess.headers.update({"User-Agent": "hafiportrait-workflow/1"})
        return cls(
            api_base_url=cfg.api_base_url,
            api_key=cfg.api_key,
            timeout_seconds=cfg.upload_timeout_seconds,
            session=sess,
        )

    def _url(self, path: str) -> str:
        return f"{self.api_base_url.rstrip('/')}/{path.lstrip('/')}"

    def fetch_events(self, source: str) -> list[dict[str, Any]]:
        """Fetch events list.

        source:
          - 'admin': /api/admin/events (requires x-api-key)
          - 'public': /api/public/events (no auth)
        """

        if source == "public":
            url = self._url("/public/events")
            headers: dict[str, str] = {}
        else:
            url = self._url("/admin/events?limit=200")
            headers = {"x-api-key": self.api_key}

        try:
            res = self.session.get(url, headers=headers, timeout=30)
            if not res.ok:
                return []
            data = res.json()

            # Shapes:
            # - admin: { data: { events: [...] } }
            # - public: { events: [...] }
            events = (data.get("data", {}).get("events")) or data.get("events") or []
            return events if isinstance(events, list) else []
        except Exception:
            return []

    def upload_jpg(self, event_id: str, path: Path) -> UploadAttemptResult:
        """Upload JPG to event upload endpoint.

        Retries/backoff are handled by the caller.
        """

        url = self._url(f"/admin/events/{event_id}/photos/upload")
        headers = {"x-api-key": self.api_key}

        ext = path.suffix.lower()
        content_type = "image/jpeg" if ext in JPG_EXTS else "application/octet-stream"

        with path.open("rb") as f:
            files = {"files": (path.name, f, content_type)}
            resp = self.session.post(url, headers=headers, files=files, timeout=self.timeout_seconds)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = None
            if isinstance(data, dict) and data.get("success") is True:
                return UploadAttemptResult(ok=True, error="ok", status_code=200)
            return UploadAttemptResult(
                ok=False,
                error=f"unexpected_response: {resp.text[:200]}",
                status_code=200,
            )

        try:
            data = resp.json()
            err = data.get("error") or data.get("message") or f"HTTP {resp.status_code}"
        except Exception:
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"

        return UploadAttemptResult(ok=False, error=err, status_code=resp.status_code)


RETRY_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)


def _should_retry(status_code: int | None) -> bool:
    return status_code in RETRY_STATUS_CODES


def _backoff_seconds(attempt: int) -> int:
    # attempt starts at 1
    return min(30, 2 ** (attempt - 1))


def upload_with_retries(cfg: Config, client: HafiportraitClient, path: Path) -> tuple[bool, str]:
    """Upload with exponential backoff retries.

    Retry policy (matching original script): retry on 429/5xx and timeouts.

    Note: `time.sleep` is called from this module scope to make it easy to
    monkeypatch in tests.
    """

    logger = get_logger(cfg)

    for attempt in range(1, cfg.upload_retries + 1):
        try:
            result = client.upload_jpg(cfg.event_id, path)
            if result.ok:
                return True, "ok"

            if _should_retry(result.status_code) and attempt < cfg.upload_retries:
                backoff = _backoff_seconds(attempt)
                log_warning(
                    cfg,
                    f"upload retry {attempt}/{cfg.upload_retries} for {path.name} after {backoff}s: {result.error}",
                )
                time.sleep(backoff)
                continue

            # Non-retryable or last attempt: log useful debug details.
            logger.debug(
                "upload failed (no retry): file=%s status=%s attempt=%s/%s err=%s",
                path.name,
                result.status_code,
                attempt,
                cfg.upload_retries,
                (result.error or "")[:200],
            )
            return False, result.error

        except requests.exceptions.Timeout:
            if attempt < cfg.upload_retries:
                backoff = _backoff_seconds(attempt)
                log_warning(cfg, f"timeout retry {attempt}/{cfg.upload_retries} for {path.name} after {backoff}s")
                time.sleep(backoff)
                continue
            logger.debug(
                "upload timeout (final): file=%s attempt=%s/%s timeout=%ss",
                path.name,
                attempt,
                cfg.upload_retries,
                cfg.upload_timeout_seconds,
            )
            return False, f"timeout > {cfg.upload_timeout_seconds}s"
        except Exception as e:
            if attempt < cfg.upload_retries:
                backoff = _backoff_seconds(attempt)
                log_warning(cfg, f"error retry {attempt}/{cfg.upload_retries} for {path.name} after {backoff}s: {e}")
                time.sleep(backoff)
                continue
            logger.debug(
                "upload error (final): file=%s attempt=%s/%s err=%s",
                path.name,
                attempt,
                cfg.upload_retries,
                str(e)[:200],
            )
            return False, str(e)

    return False, "failed"
