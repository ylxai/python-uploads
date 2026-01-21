from __future__ import annotations

from pathlib import Path

import requests

import hafiportrait_workflow.api as api
from hafiportrait_workflow.api import HafiportraitClient, UploadAttemptResult, upload_with_retries
from hafiportrait_workflow.models import Config


def _cfg(tmp_path: Path, retries: int = 3) -> Config:
    root = tmp_path
    return Config(
        api_base_url="https://example.invalid/api",
        api_key="k",
        event_id="event",
        poll_seconds=1.0,
        file_stable_seconds=0.0,
        incoming=root / "incoming",
        raw=root / "raw",
        jpg_in=root / "jpg_in",
        uploaded=root / "uploaded",
        failed=root / "failed",
        tmp=root / "tmp",
        state_path=root / "state" / "state.json",
        logs_path=root / "logs",
        log_level="INFO",
        upload_timeout_seconds=1,
        upload_retries=retries,
        frame_enabled=False,
        frame_landscape_path=None,
        frame_portrait_path=None,
    )


class DummyClient(HafiportraitClient):
    def __init__(self, results: list[UploadAttemptResult]):
        self._results = results
        super().__init__(
            api_base_url="https://example.invalid/api",
            api_key="k",
            timeout_seconds=1,
            session=requests.Session(),
        )

    def upload_jpg(self, event_id: str, path: Path) -> UploadAttemptResult:  # type: ignore[override]
        return self._results.pop(0)


def test_upload_with_retries_retries_on_5xx(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path, retries=3)

    # 500 then ok
    client = DummyClient(
        [
            UploadAttemptResult(ok=False, error="server", status_code=500),
            UploadAttemptResult(ok=True, error="ok", status_code=200),
        ]
    )

    slept: list[float] = []

    def fake_sleep(s: float) -> None:
        slept.append(s)

    monkeypatch.setattr(api.time, "sleep", fake_sleep)

    f = tmp_path / "x.jpg"
    f.write_bytes(b"data")

    ok, err = upload_with_retries(cfg, client, f)
    assert ok is True
    assert err == "ok"
    assert slept == [1]  # first backoff for attempt 1


def test_upload_with_retries_no_retry_on_400(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path, retries=3)
    client = DummyClient([UploadAttemptResult(ok=False, error="bad", status_code=400)])

    monkeypatch.setattr(api.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("should not sleep")))

    f = tmp_path / "x.jpg"
    f.write_bytes(b"data")

    ok, err = upload_with_retries(cfg, client, f)
    assert ok is False
    assert err == "bad"


def test_upload_with_retries_timeout(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path, retries=2)

    class TimeoutClient(DummyClient):
        def upload_jpg(self, event_id: str, path: Path) -> UploadAttemptResult:  # type: ignore[override]
            raise requests.exceptions.Timeout()

    client = TimeoutClient([])

    slept: list[float] = []
    monkeypatch.setattr(api.time, "sleep", lambda s: slept.append(s))

    f = tmp_path / "x.jpg"
    f.write_bytes(b"data")

    ok, err = upload_with_retries(cfg, client, f)
    assert ok is False
    assert "timeout" in err
    assert slept == [1]
