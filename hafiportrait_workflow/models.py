from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Config:
    api_base_url: str
    api_key: str
    event_id: str

    poll_seconds: float
    file_stable_seconds: float

    incoming: Path
    raw: Path
    jpg_in: Path
    uploaded: Path
    failed: Path
    tmp: Path
    state_path: Path
    logs_path: Path

    log_level: str

    upload_timeout_seconds: int
    upload_retries: int

    frame_enabled: bool
    frame_landscape_path: str | None
    frame_portrait_path: str | None
