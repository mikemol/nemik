# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2164: check.copy_letter copies a letter's bytes, permission bits and times, atomically.

nemik.check used shutil.copy2 for the one place it redelivers a letter, and shutil is a Codon wall;
the copy is now plain pathlib and os. A letter's content, mode and modification time are what a
reader of the recipient's inbox sees, so the tests pin those three. The copy is also atomic, which
copy2 is not: the bytes go to a sibling temp name and os.replace puts the whole file onto the
destination, so a destination that already exists is never seen partially written. os.replace
makes that true by construction, so the sequence is asserted through a seam (os.replace itself).
"""

import os
import pathlib
import stat
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from nemik.check import PERMISSION_BITS, copy_letter

if TYPE_CHECKING:
    from pathlib import Path

OLD_NS = 1_700_000_000_123_456_789
MODE = 0o640
LETTER = b"to: nemik\n\nan \xc3\xa9 and a newline\n"


def test_the_copy_keeps_the_bytes_the_mode_and_the_times(tmp_path: Path) -> None:
    """Carry content, permission bits and the modification time from source to destination."""
    src = tmp_path / "from.md"
    src.write_bytes(LETTER)
    src.chmod(MODE)
    os.utime(src, ns=(OLD_NS, OLD_NS))
    dst = tmp_path / "to.md"
    copy_letter(src, dst)
    assert dst.read_bytes() == LETTER
    assert stat.S_IMODE(dst.stat().st_mode) == MODE
    assert dst.stat().st_mtime_ns == OLD_NS
    assert src.read_bytes() == LETTER


def test_the_copy_replaces_an_older_destination(tmp_path: Path) -> None:
    """Overwrite what was there, never append to it."""
    src = tmp_path / "from.md"
    src.write_bytes(b"new")
    dst = tmp_path / "to.md"
    dst.write_bytes(b"older and longer")
    copy_letter(src, dst)
    assert dst.read_bytes() == b"new"


def test_the_permission_mask_keeps_only_the_mode_bits() -> None:
    """Mask the file type off st_mode, as os.chmod takes only the permission bits."""
    assert PERMISSION_BITS & stat.S_IFREG == 0
    assert PERMISSION_BITS & stat.S_IRWXU == stat.S_IRWXU


def test_an_existing_destination_is_whole_until_the_replace(tmp_path: Path) -> None:
    """Hold the old destination untouched until os.replace, which then gets a complete temp file."""
    src = tmp_path / "from.md"
    src.write_bytes(LETTER)
    src.chmod(MODE)
    os.utime(src, ns=(OLD_NS, OLD_NS))
    dst = tmp_path / "to.md"
    dst.write_bytes(b"the older whole letter")
    real = pathlib.Path.replace
    seen: dict[str, object] = {}

    def watching_replace(part: Path, target: Path) -> Path:
        seen["dst_then"] = target.read_bytes()
        seen["part_bytes"] = part.read_bytes()
        seen["part_mode"] = stat.S_IMODE(part.stat().st_mode)
        seen["part_mtime"] = part.stat().st_mtime_ns
        seen["same_dir"] = part.parent == target.parent
        return real(part, target)

    with mock.patch.object(pathlib.Path, "replace", watching_replace):
        copy_letter(src, dst)
    assert seen["dst_then"] == b"the older whole letter"
    assert seen["part_bytes"] == LETTER
    assert seen["part_mode"] == MODE
    assert seen["part_mtime"] == OLD_NS
    assert seen["same_dir"] is True
    assert dst.read_bytes() == LETTER


def test_a_failure_before_the_replace_leaves_the_destination_and_no_temp(
    tmp_path: Path,
) -> None:
    """Keep the older destination whole and remove the temp file when the replace fails."""
    src = tmp_path / "from.md"
    src.write_bytes(LETTER)
    dst = tmp_path / "to.md"
    dst.write_bytes(b"the older whole letter")

    def failing_replace(part: Path, target: Path) -> Path:
        del part, target
        message = "the disk went away"
        raise OSError(message)

    with (
        mock.patch.object(pathlib.Path, "replace", failing_replace),
        pytest.raises(OSError, match="disk"),
    ):
        copy_letter(src, dst)
    assert dst.read_bytes() == b"the older whole letter"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["from.md", "to.md"]
