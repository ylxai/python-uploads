from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .api import HafiportraitClient, upload_with_retries
from .constants import JPG_EXTS, RAW_EXTS
from .fs_utils import ensure_dirs, file_signature, is_file_stable, safe_move
from .logging_utils import get_logger
from .models import Config
from .state import load_state, save_state
from .state_models import MovedRawRecord, QueuedJpgRecord, StateDict, is_uploaded
from .workflows.simple import LoggerLike, UploaderFn, queue_jpg, upload_queued_jpg

SleepFn = Callable[[float], None]


def make_state_key(path: Path) -> str:
    name, size, mtime = file_signature(path)
    return f"{name}::{size}::{mtime}"


def is_already_uploaded(state: StateDict, key: str) -> bool:
    rec = state.get(key)
    return is_uploaded(rec) if rec is not None else False


def handle_raw(cfg: Config, state: StateDict, key: str, src: Path, logger: LoggerLike) -> None:
    moved = safe_move(src, cfg.raw)
    state[key] = MovedRawRecord(status="moved_raw", path=str(moved))
    save_state(cfg, state)
    logger.info(f"RAW moved: {moved.name}")


def ingest_jpg(cfg: Config, state: StateDict, src: Path, logger: LoggerLike) -> None:
    moved = queue_jpg(cfg, src, logger)
    key = make_state_key(moved)
    state[key] = QueuedJpgRecord(status="queued_jpg", path=str(moved))
    save_state(cfg, state)


def upload_from_queue(cfg: Config, state: StateDict, key: str, queued_path: Path, uploader: UploaderFn, logger: LoggerLike) -> None:
    upload_queued_jpg(cfg=cfg, state=state, key=key, queued_path=queued_path, uploader=uploader, logger=logger)
    save_state(cfg, state)


def ingest_incoming_file(
    *,
    cfg: Config,
    state: StateDict,
    path: Path,
    logger: LoggerLike,
) -> None:
    if not path.is_file():
        logger.debug(f"skip non-file: {path}")
        return

    ext = path.suffix.lower()

    if not is_file_stable(path, cfg.file_stable_seconds):
        logger.debug(f"skip not stable yet: {path.name}")
        return

    if ext in RAW_EXTS:
        # For RAW we can keep a signature-based key on the incoming file.
        key = make_state_key(path)
        if is_already_uploaded(state, key):
            logger.debug(f"skip already uploaded: {path.name} key={key}")
            return
        handle_raw(cfg, state, key, path, logger)
        return

    if ext in JPG_EXTS:
        # Queue mode: key is based on the queued file signature in jpg_in.
        ingest_jpg(cfg, state, path, logger)
        return

    logger.debug(f"skip unknown extension: {path.name} ext={ext}")
    # Unknown extension -> ignore


def ingest_iteration(*, cfg: Config, state: StateDict, logger: LoggerLike) -> None:
    """Fast ingest: move files from incoming/ into raw/ or jpg_in/."""

    for path in sorted(cfg.incoming.iterdir()):
        ingest_incoming_file(cfg=cfg, state=state, path=path, logger=logger)


def upload_iteration(*, cfg: Config, state: StateDict, uploader: UploaderFn, logger: LoggerLike) -> tuple[int, int, dict[str, int]]:
    """Upload worker: process backlog in jpg_in/.

    Returns:
      (uploaded_ok, failed, fail_categories)
    """

    from .error_reporting import classify_upload_failure, extract_status_code

    ok_count = 0
    fail_count = 0
    fail_categories: dict[str, int] = {}

    for path in sorted(cfg.jpg_in.iterdir()):
        if not path.is_file():
            continue
        if not is_file_stable(path, cfg.file_stable_seconds):
            logger.debug(f"queue not stable yet: {path.name}")
            continue

        key = make_state_key(path)
        if is_already_uploaded(state, key):
            continue

        # Process/upload
        upload_from_queue(cfg, state, key, path, uploader, logger)

        rec = state.get(key)
        if rec and rec.get("status") == "uploaded":
            ok_count += 1
        elif rec and rec.get("status") == "failed":
            fail_count += 1
            reason = str(rec.get("reason", ""))
            code = extract_status_code(reason)
            cat = classify_upload_failure(code, reason)
            fail_categories[cat] = fail_categories.get(cat, 0) + 1

    return ok_count, fail_count, fail_categories


def run_watch(cfg: Config, *, sleep_fn: SleepFn = time.sleep) -> None:
    ensure_dirs(
        cfg.incoming,
        cfg.raw,
        cfg.jpg_in,
        cfg.uploaded,
        cfg.failed,
        cfg.tmp,
        cfg.logs_path,
        cfg.state_path.parent,
    )

    state = load_state(cfg)
    client = HafiportraitClient.from_config(cfg)

    logger = get_logger(cfg)
    uploader: UploaderFn = lambda p: upload_with_retries(cfg, client, p)

    logger.info(f"SIMPLE watch started root={cfg.incoming.parent} event_id={cfg.event_id}")

    last_summary = time.monotonic()
    summary_interval = 60.0

    total_ok = 0
    total_failed = 0
    total_fail_categories: dict[str, int] = {}

    while True:
        try:
            ingest_iteration(cfg=cfg, state=state, logger=logger)
            uploaded_ok, failed, fail_categories = upload_iteration(cfg=cfg, state=state, uploader=uploader, logger=logger)

            total_ok += uploaded_ok
            total_failed += failed
            for k, v in fail_categories.items():
                total_fail_categories[k] = total_fail_categories.get(k, 0) + v

            now = time.monotonic()
            if now - last_summary >= summary_interval:
                try:
                    backlog = sum(1 for p in cfg.jpg_in.iterdir() if p.is_file())
                except Exception:
                    backlog = -1
                cats = " ".join(f"{k}={v}" for k, v in sorted(fail_categories.items()))
                suffix = f" ({cats})" if cats else ""
                logger.info(f"SUMMARY: backlog={backlog} uploaded_ok+{uploaded_ok} failed+{failed}{suffix}")
                last_summary = now

            sleep_fn(cfg.poll_seconds)

        except KeyboardInterrupt:
            try:
                backlog = sum(1 for p in cfg.jpg_in.iterdir() if p.is_file())
            except Exception:
                backlog = -1

            cats = " ".join(f"{k}={v}" for k, v in sorted(total_fail_categories.items()))
            suffix = f" ({cats})" if cats else ""
            logger.info(
                f"FINAL SUMMARY: backlog={backlog} total_uploaded_ok={total_ok} total_failed={total_failed}{suffix}"
            )
            logger.info("Stopped by user")
            return
        except Exception as e:
            logger.error(f"Loop error: {e}")
            sleep_fn(cfg.poll_seconds)
