from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from PIL import Image

from ..fs_utils import safe_move, validate_jpg
from ..models import Config
from ..state_models import FailedRecord, StateDict, UploadedRecord
from .frame import apply_frame_landscape


class LoggerLike(Protocol):
    def debug(self, msg: str) -> None: ...

    def info(self, msg: str) -> None: ...

    def warning(self, msg: str) -> None: ...

    def error(self, msg: str) -> None: ...


UploaderFn = Callable[[Path], tuple[bool, str]]


def queue_jpg(cfg: Config, src: Path, logger: LoggerLike) -> Path:
    moved = safe_move(src, cfg.jpg_in)
    logger.info(f"JPG queued: {moved.name}")
    return moved


def upload_queued_jpg(
    *,
    cfg: Config,
    state: StateDict,
    key: str,
    queued_path: Path,
    uploader: UploaderFn,
    logger: LoggerLike,
) -> None:
    """Upload a JPG file that is already in jpg_in/.

    If frame is enabled and photo is landscape, apply frame before upload.
    """

    if not validate_jpg(queued_path):
        failed_path = safe_move(queued_path, cfg.failed)
        state[key] = FailedRecord(status="failed", reason="invalid_jpg", path=str(failed_path))
        logger.warning(f"JPG invalid -> failed: {failed_path.name}")
        return

    # Determine upload source: framed or original
    upload_path = queued_path

    if cfg.frame_enabled and cfg.frame_landscape_path:
        # Check if landscape
        try:
            with Image.open(queued_path) as im:
                w, h = im.size
            is_landscape = w > h
        except Exception:
            is_landscape = False

        if is_landscape:
            frame_path = Path(cfg.frame_landscape_path)
            if not frame_path.is_absolute():
                # Relative to root (where config.json is)
                root = queued_path.parents[1]  # jpg_in is 1 level below root
                frame_path = root / frame_path

            if frame_path.exists():
                # Apply frame
                cfg.tmp.mkdir(parents=True, exist_ok=True)
                framed_path = cfg.tmp / f"framed_{queued_path.name}"

                try:
                    apply_frame_landscape(queued_path, frame_path, framed_path)
                    upload_path = framed_path
                    logger.debug(f"applied landscape frame: {queued_path.name}")
                except Exception as e:
                    logger.warning(f"frame failed for {queued_path.name}: {e}, uploading original")
            else:
                logger.debug(f"frame file not found: {frame_path}, uploading original")

    # Upload
    ok, err = uploader(upload_path)

    # Cleanup temp framed file if used
    if upload_path != queued_path and upload_path.exists():
        try:
            upload_path.unlink()
        except Exception:
            pass

    if ok:
        # Keep original in jpg_in (backup), mark as uploaded
        state[key] = UploadedRecord(status="uploaded", path=str(queued_path))
        logger.info(f"UPLOAD OK: {queued_path.name}")
        return

    failed_path = safe_move(queued_path, cfg.failed)
    state[key] = FailedRecord(status="failed", reason=err, path=str(failed_path))
    logger.error(f"UPLOAD FAIL: {failed_path.name} ({err})")


def process_jpg_simple(
    *,
    cfg: Config,
    state: StateDict,
    key: str,
    src: Path,
    uploader: UploaderFn,
    logger: LoggerLike,
) -> None:
    """SIMPLE mode JPG pipeline: queue -> validate -> upload -> move result -> update state."""

    moved = queue_jpg(cfg, src, logger)
    upload_queued_jpg(cfg=cfg, state=state, key=key, queued_path=moved, uploader=uploader, logger=logger)
