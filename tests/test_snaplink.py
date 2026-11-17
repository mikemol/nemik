# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2063: unchanged files are shared between snapshots, so the volume counts them once."""

import os
from pathlib import Path

import pytest

from nemik.serve import publish
from nemik.snaplink import link_unchanged

FLEET = Path(__file__).parent / "fixtures" / "fleet"
LINKED_TWICE = 2


def _tree(root: Path, files: dict[str, str]) -> Path:
    """Write the named files, with their text, under `root`.

    Returns:
        The directory.

    """
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _inode(path: Path) -> int:
    """Name a file's inode, which two hard links share.

    Returns:
        The inode number.

    """
    return path.stat().st_ino


def test_an_unchanged_file_becomes_a_link_and_a_changed_one_stays(
    tmp_path: Path,
) -> None:
    """Same bytes at the same path share an inode; different bytes do not; a new file stays."""
    before = _tree(
        tmp_path / "before", {"a.txt": "same", "b.txt": "old", "sub/c.txt": "deep"}
    )
    snap = _tree(
        tmp_path / "snap",
        {"a.txt": "same", "b.txt": "new", "sub/c.txt": "deep", "d.txt": "x"},
    )
    assert link_unchanged(snap, before) == LINKED_TWICE
    assert _inode(snap / "a.txt") == _inode(before / "a.txt")
    assert _inode(snap / "sub" / "c.txt") == _inode(before / "sub" / "c.txt")
    assert _inode(snap / "b.txt") != _inode(before / "b.txt")
    assert (snap / "b.txt").read_text(encoding="utf-8") == "new"
    assert (snap / "d.txt").read_text(encoding="utf-8") == "x"


def test_a_second_pass_links_nothing_more(tmp_path: Path) -> None:
    """A file that already shares an inode is not counted again."""
    before = _tree(tmp_path / "before", {"a.txt": "same"})
    snap = _tree(tmp_path / "snap", {"a.txt": "same"})
    assert link_unchanged(snap, before) == 1
    assert link_unchanged(snap, before) == 0


def test_a_missing_previous_directory_is_not_walked(tmp_path: Path) -> None:
    """A snapshot with no predecessor under a directory keeps its own copy."""
    before = _tree(tmp_path / "before", {"a.txt": "same"})
    snap = _tree(tmp_path / "snap", {"a.txt": "same", "sub/c.txt": "deep"})
    assert link_unchanged(snap, before) == 1
    assert (snap / "sub" / "c.txt").read_text(encoding="utf-8") == "deep"


def test_a_symlink_is_left_as_built(tmp_path: Path) -> None:
    """A link in the snapshot is not replaced by a link to the previous one's target."""
    before = _tree(tmp_path / "before", {"a.txt": "same"})
    snap = _tree(tmp_path / "snap", {"real.txt": "same"})
    (snap / "a.txt").symlink_to("real.txt")
    assert link_unchanged(snap, before) == 0
    assert (snap / "a.txt").is_symlink()


def test_a_publish_shares_what_the_previous_snapshot_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two publishes over one fleet: the second snapshot shares inodes with the first.

    The view is rebuilt on a stale key, in a process the test gives a second pid so the two
    snapshots are two directories, and every file but source-key is the same bytes.
    """
    base = tmp_path / "pub"
    first = publish(FLEET, base, None)
    assert first is not None
    (base / "current" / "source-key").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(os, "getpid", lambda: 424242)
    second = publish(FLEET, base, None)
    assert second is not None
    assert second != first
    shared = [
        p
        for p in second.rglob("*")
        if p.is_file()
        and not p.is_symlink()
        and (first / p.relative_to(second)).is_file()
        and _inode(p) == _inode(first / p.relative_to(second))
    ]
    assert shared
    assert (second / "source-key").read_text(encoding="utf-8") != "stale"
    assert _inode(second / "source-key") != _inode(first / "source-key")
