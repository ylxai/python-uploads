from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

from .api import HafiportraitClient
from .interactive import interactive_select_event
from .models import Config
from .errors import MissingApiKeyError, MissingEventIdError, MissingLastEventError
from .state import load_last_event, save_last_event


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    # More strict: block common placeholders.
    return ("YOUR_" in v) or ("EVENT_UUID" in v)


def load_config_json(root: Path) -> dict[str, Any]:
    """Load local config.json (ignored by git)."""

    path = root / "config.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_str(data: dict[str, Any], key: str) -> str:
    v = data.get(key)
    return v if isinstance(v, str) else ""


def _get_nested(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _get_nested_str(data: dict[str, Any], *keys: str) -> str:
    v = _get_nested(data, *keys)
    return v if isinstance(v, str) else ""


def _get_nested_number(data: dict[str, Any], *keys: str) -> float | int | None:
    v = _get_nested(data, *keys)
    if isinstance(v, (int, float)):
        return v
    return None


def resolve_setting(cli_value: str, env_value: str, cfg_value: str) -> str:
    """Resolve with priority CLI > env > config.json."""

    if cli_value:
        return cli_value
    if env_value:
        return env_value
    return cfg_value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hafiportrait standalone photographer workflow (SIMPLE mode)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Interactive: pick event from public list (no API key needed for listing)\n"
            "  python3 run.py --interactive --events-source public\n\n"
            "  # Non-interactive: provide event UUID\n"
            "  python3 run.py --api-key <API_KEY> --event-id <EVENT_UUID>\n\n"
            "  # Non-interactive: use last event UUID\n"
            "  python3 run.py --api-key <API_KEY> --use-last-event\n"
        ),
    )

    # Default root should match the legacy script: folder where run.py lives.
    # Since `run.py` imports this package, we set default to the workspace root
    # (parent of this package directory).
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Root folder (contains incoming/raw/jpg_in/etc)",
    )

    # CLI values. Env/config.json are applied later in `resolve_args_interactive`.
    parser.add_argument(
        "--api-base-url",
        default="",
        help="API base URL (or set HAFI_API_BASE_URL / config.json api_base_url)",
    )
    parser.add_argument("--api-key", default="", help="API key (or set HAFI_API_KEY / config.json api_key)")
    parser.add_argument("--event-id", default="", help="Event UUID (or set HAFI_EVENT_ID / config.json event_id)")

    parser.add_argument("--poll-seconds", type=float, default=0.0)
    parser.add_argument("--file-stable-seconds", type=float, default=0.0)

    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--retries", type=int, default=0)

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for missing API key and event selection interactively",
    )
    parser.add_argument(
        "--events-source",
        choices=["admin", "public"],
        default="",
        help="Where to load events list from (admin requires API key; public does not).\n"
        "If omitted, uses HAFI_EVENTS_SOURCE or config.json (events_source) or 'admin'.",
    )

    parser.add_argument(
        "--log-level",
        default="",
        help="Log level (DEBUG, INFO, WARNING, ERROR).\n"
        "If omitted, uses HAFI_LOG_LEVEL or config.json logging.level or INFO.",
    )
    parser.add_argument(
        "--use-last-event",
        action="store_true",
        help="Use state/last_event.json event_id without prompting (fails if not found)",
    )

    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> Config:
    root = Path(args.root).resolve()
    cfg_data = load_config_json(root)

    def p(name: str) -> Path:
        return root / name

    # api_base_url
    api_base_url = resolve_setting(
        args.api_base_url,
        os.environ.get("HAFI_API_BASE_URL", ""),
        _get_str(cfg_data, "api_base_url"),
    ) or "https://hafiportrait.photography/api"

    # numeric settings (CLI > env > config.json > default)
    poll_seconds = args.poll_seconds or float(
        os.environ.get(
            "HAFI_POLL_SECONDS",
            str(_get_nested_number(cfg_data, "watch", "poll_seconds") or "2"),
        )
    )
    file_stable_seconds = args.file_stable_seconds or float(
        os.environ.get(
            "HAFI_FILE_STABLE_SECONDS",
            str(_get_nested_number(cfg_data, "watch", "file_stable_seconds") or "2"),
        )
    )
    timeout_seconds = args.timeout_seconds or int(
        os.environ.get(
            "HAFI_UPLOAD_TIMEOUT_SECONDS",
            str(_get_nested_number(cfg_data, "upload", "timeout_seconds") or "120"),
        )
    )
    retries = args.retries or int(
        os.environ.get(
            "HAFI_UPLOAD_RETRIES",
            str(_get_nested_number(cfg_data, "upload", "retries") or "3"),
        )
    )

    # logging
    log_level = (
        resolve_setting(
            getattr(args, "log_level", ""),
            os.environ.get("HAFI_LOG_LEVEL", ""),
            _get_nested_str(cfg_data, "logging", "level"),
        )
        or "INFO"
    )

    # frame
    frame_enabled_val = _get_nested(cfg_data, "frame", "enabled")
    if isinstance(frame_enabled_val, bool):
        frame_enabled = frame_enabled_val
    elif isinstance(frame_enabled_val, str):
        frame_enabled = frame_enabled_val.lower() in ("true", "1", "yes")
    else:
        frame_enabled = False
    
    frame_landscape = _get_nested_str(cfg_data, "frame", "landscape") or None
    frame_portrait = _get_nested_str(cfg_data, "frame", "portrait") or None

    return Config(
        api_base_url=api_base_url,
        api_key=args.api_key,
        event_id=args.event_id,
        poll_seconds=poll_seconds,
        file_stable_seconds=file_stable_seconds,
        incoming=p("incoming"),
        raw=p("raw"),
        jpg_in=p("jpg_in"),
        uploaded=p("uploaded"),
        failed=p("failed"),
        tmp=p("tmp"),
        state_path=p("state") / "state.json",
        logs_path=p("logs"),
        log_level=log_level,
        upload_timeout_seconds=timeout_seconds,
        upload_retries=retries,
        frame_enabled=frame_enabled,
        frame_landscape_path=frame_landscape,
        frame_portrait_path=frame_portrait,
    )


def resolve_api_base_url(args: argparse.Namespace, cfg_data: dict[str, Any]) -> str:
    return (
        resolve_setting(
            args.api_base_url,
            os.environ.get("HAFI_API_BASE_URL", ""),
            _get_str(cfg_data, "api_base_url"),
        )
        or "https://hafiportrait.photography/api"
    )


def resolve_events_source(args: argparse.Namespace, cfg_data: dict[str, Any]) -> str:
    src = (
        resolve_setting(
            args.events_source,
            os.environ.get("HAFI_EVENTS_SOURCE", ""),
            _get_str(cfg_data, "events_source") or _get_nested_str(cfg_data, "events", "source"),
        )
        or "admin"
    )
    return src if src in ("admin", "public") else "admin"


def resolve_api_key(args: argparse.Namespace, cfg_data: dict[str, Any]) -> str:
    api_key = resolve_setting(args.api_key, os.environ.get("HAFI_API_KEY", ""), _get_str(cfg_data, "api_key"))
    return "" if _is_placeholder(api_key) else api_key


def resolve_event_id(args: argparse.Namespace, cfg_data: dict[str, Any]) -> str:
    event_id = resolve_setting(args.event_id, os.environ.get("HAFI_EVENT_ID", ""), _get_str(cfg_data, "event_id"))
    return "" if _is_placeholder(event_id) else event_id


def apply_use_last_event(root: Path, event_id: str) -> str:
    last = load_last_event(root)
    if not last:
        raise MissingLastEventError(
            "No last event found (state/last_event.json). Run --interactive once or provide --event-id/config.json."
        )
    return last


def maybe_interactive_select_event(
    *,
    root: Path,
    api_base_url: str,
    api_key: str,
    events_source: str,
) -> str:
    sess = requests.Session()
    sess.headers.update({"User-Agent": "hafiportrait-workflow/1"})
    client = HafiportraitClient(
        api_base_url=api_base_url,
        api_key=api_key,
        timeout_seconds=30,
        session=sess,
    )
    event_id = interactive_select_event(client, events_source, root)
    save_last_event(root, event_id)
    return event_id


def resolve_args_interactive(args: argparse.Namespace) -> argparse.Namespace:
    """Resolve settings from CLI/env/config.json and handle interactive flags.

    Priority for config values:
      CLI flags > environment variables > config.json

    Validation (strict): values containing 'YOUR_' or 'EVENT_UUID' are treated as missing.
    """

    root = Path(args.root).resolve()
    cfg_data = load_config_json(root)

    api_base_url = resolve_api_base_url(args, cfg_data)
    events_source = resolve_events_source(args, cfg_data)
    api_key = resolve_api_key(args, cfg_data)
    event_id = resolve_event_id(args, cfg_data)

    args.api_base_url = api_base_url
    args.events_source = events_source

    if args.use_last_event and not event_id:
        event_id = apply_use_last_event(root, event_id)

    if args.interactive and not event_id:
        event_id = maybe_interactive_select_event(
            root=root,
            api_base_url=api_base_url,
            api_key=api_key,
            events_source=events_source,
        )

    # Strict behavior (b): do NOT prompt for api_key. Require it to be configured.
    if not api_key:
        raise MissingApiKeyError(
            "Missing API key. Set it via --api-key, HAFI_API_KEY, or config.json (api_key)."
        )
    if not event_id:
        raise MissingEventIdError(
            "Missing event id (UUID). Set it via --event-id, HAFI_EVENT_ID, config.json (event_id), or run with --interactive."
        )

    args.api_key = api_key
    args.event_id = event_id

    return args
