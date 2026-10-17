# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W642: the cache store under two writers and a run that was killed mid-write."""

import os
from pathlib import Path

from nemik import cachestore


def test_two_writers_leave_both_builds_loadable(tmp_path: Path) -> None:
    """Two builds saving into one directory under different names do not disturb each other."""
    cachestore.save(tmp_path, "build-caches-aaaaaaaaaaaaaaaa.pickle")
    cachestore.save(tmp_path, cachestore.user_name())
    assert cachestore.load(tmp_path, cachestore.user_name())
    assert (tmp_path / "build-caches-aaaaaaaaaaaaaaaa.pickle").exists()


def test_a_stale_temp_file_from_a_killed_run_is_swept(tmp_path: Path) -> None:
    """A temp file older than the stray age goes; a fresh one (a live writer's) stays."""
    old = tmp_path / ".build-caches-0000000000000000.pickle.111"
    fresh = tmp_path / ".build-caches-1111111111111111.pickle.222"
    old.write_bytes(b"x")
    fresh.write_bytes(b"x")
    os.utime(old, (1_000_000, 1_000_000))
    cachestore.prune(tmp_path)
    assert not old.exists()
    assert fresh.exists()


def test_a_directory_that_does_not_exist_is_ignored(tmp_path: Path) -> None:
    """Prune on a missing directory does nothing and does not raise."""
    cachestore.prune(tmp_path / "missing")
