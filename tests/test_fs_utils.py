from __future__ import annotations

from pathlib import Path

from hafiportrait_workflow.fs_utils import safe_move


def test_safe_move_avoids_overwrite(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()

    src1 = src_dir / "photo.jpg"
    src1.write_bytes(b"a")

    moved1 = safe_move(src1, dst_dir)
    assert moved1.name == "photo.jpg"
    assert moved1.read_bytes() == b"a"

    src2 = src_dir / "photo.jpg"
    src2.write_bytes(b"b")

    moved2 = safe_move(src2, dst_dir)
    assert moved2.name.startswith("photo__")
    assert moved2.suffix == ".jpg"
    assert moved2.read_bytes() == b"b"
