from __future__ import annotations

import json
from pathlib import Path

from hafiportrait_workflow.models import Config
from hafiportrait_workflow.state import load_state, save_state


def _cfg(tmp_path: Path) -> Config:
    root = tmp_path
    return Config(
        api_base_url="https://example.invalid/api",
        api_key="k",
        event_id="e",
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
        upload_retries=3,
        frame_enabled=False,
        frame_landscape_path=None,
        frame_portrait_path=None,
    )


def test_save_state_atomic(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    state = {"a": {"status": "uploaded"}}
    save_state(cfg, state)

    # file exists and is valid json
    loaded_text = cfg.state_path.read_text(encoding="utf-8")
    assert json.loads(loaded_text) == state

    # no lingering tmp file
    assert not cfg.state_path.with_suffix(".tmp").exists()

    # load_state reads it back
    assert load_state(cfg) == state
