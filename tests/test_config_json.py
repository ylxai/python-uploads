from __future__ import annotations

import json
from pathlib import Path

import pytest

from hafiportrait_workflow.config import build_config, parse_args, resolve_args_interactive
from hafiportrait_workflow.errors import ConfigError


def test_config_json_used_when_no_cli_or_env(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "api_base_url": "https://example.invalid/api",
        "api_key": "k_from_cfg",
        "event_id": "e_from_cfg",
        "watch": {"poll_seconds": 5, "file_stable_seconds": 6},
        "upload": {"timeout_seconds": 7, "retries": 8},
        "logging": {"level": "DEBUG"},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.delenv("HAFI_API_KEY", raising=False)
    monkeypatch.delenv("HAFI_EVENT_ID", raising=False)
    monkeypatch.delenv("HAFI_API_BASE_URL", raising=False)

    args = parse_args(["--root", str(tmp_path)])
    args = resolve_args_interactive(args)

    assert args.api_key == "k_from_cfg"
    assert args.event_id == "e_from_cfg"
    assert args.api_base_url == "https://example.invalid/api"

    cfg_obj = build_config(args)
    assert cfg_obj.log_level == "DEBUG"


def test_cli_overrides_env_overrides_config(tmp_path: Path, monkeypatch) -> None:
    cfg = {"api_key": "k_cfg", "event_id": "e_cfg"}
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.setenv("HAFI_API_KEY", "k_env")
    monkeypatch.setenv("HAFI_EVENT_ID", "e_env")

    args = parse_args(["--root", str(tmp_path), "--api-key", "k_cli", "--event-id", "e_cli"])
    args = resolve_args_interactive(args)

    assert args.api_key == "k_cli"
    assert args.event_id == "e_cli"


def test_placeholder_is_invalid_and_errors(tmp_path: Path, monkeypatch) -> None:
    cfg = {"api_key": "YOUR_API_KEY", "event_id": "EVENT_UUID"}
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.delenv("HAFI_API_KEY", raising=False)
    monkeypatch.delenv("HAFI_EVENT_ID", raising=False)

    args = parse_args(["--root", str(tmp_path)])
    with pytest.raises(ConfigError):
        resolve_args_interactive(args)
