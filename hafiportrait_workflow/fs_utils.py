from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Tuple


def file_signature(path: Path) -> Tuple[str, int, int]:
    st = path.stat()
    return (path.name, st.st_size, int(st.st_mtime))


def is_file_stable(path: Path, stable_seconds: float) -> bool:
    """Return True when file size has not changed after stable_seconds."""

    try:
        s1 = path.stat().st_size
    except FileNotFoundError:
        return False

    time.sleep(stable_seconds)

    try:
        s2 = path.stat().st_size
    except FileNotFoundError:
        return False

    return s1 == s2 and s2 > 0


def validate_jpg(path: Path) -> bool:
    """Verify JPEG is readable (not corrupted/partial).

    Pillow (PIL) is an explicit dependency. Import is done lazily so the CLI can
    still show `--help` even if dependencies are not installed yet.
    """

    try:
        from PIL import Image  # type: ignore
    except Exception:
        # If Pillow isn't installed, we can't validate. Treat as invalid so the
        # operator gets an actionable outcome (install requirements).
        return False

    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def safe_move(src: Path, dst_dir: Path) -> Path:
    """Move src into dst_dir, avoiding overwrite by adding a counter suffix."""

    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name

    if dst.exists():
        stem, suf = src.stem, src.suffix
        i = 1
        while True:
            candidate = dst_dir / f"{stem}__{i}{suf}"
            if not candidate.exists():
                dst = candidate
                break
            i += 1

    shutil.move(str(src), str(dst))
    return dst


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
