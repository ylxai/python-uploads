from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import Config
from .state_models import StateDict


def load_state(cfg: Config) -> StateDict:
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.state_path.exists():
        return {}
    try:
        raw = json.loads(cfg.state_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_state(cfg: Config, state: StateDict) -> None:
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg.state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(cfg.state_path)


def last_event_path(root: Path) -> Path:
    return root / "state" / "last_event.json"


def save_last_event(root: Path, event_id: str) -> None:
    p = last_event_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"event_id": event_id}, indent=2), encoding="utf-8")
    tmp.replace(p)


def load_last_event(root: Path) -> Optional[str]:
    p = last_event_path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        v = data.get("event_id")
        return v if isinstance(v, str) and v else None
    except Exception:
        return None
