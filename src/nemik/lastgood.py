# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1086: the last good snapshot, kept on the claim, so a restarted pod serves at once.

A pod's snapshots live in an emptyDir that dies with it, and the server container answers 503 on
/metrics until one snapshot exists. A fresh pod therefore stays unready for a whole cold build, and
a build killed by the memory limit (luthen-observability W1651) leaves the Service with no endpoint
and every nemik gauge dark. The builder copies each good snapshot to the persistent claim, and a
new pod restores the latest one at once, then builds as before; the data may be a build old, never
absent. Only os and pathlib, no shutil, so the Codon census compiles it.
"""

import os
from pathlib import Path

LAST = "last-good"
# the new copy and the one before it, so a reader of the old link keeps its files
KEEP = 2


def _age(path: Path) -> float:
    return path.stat().st_mtime


def _copy(src: Path, dst: Path) -> None:
    """Copy a directory tree, links kept as links."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_symlink():
            target.symlink_to(item.readlink())
        elif item.is_dir():
            _copy(item, target)
        else:
            target.write_bytes(item.read_bytes())


def _remove(path: Path) -> None:
    """Delete a directory tree; a missing one is nothing to do."""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        for item in path.iterdir():
            _remove(item)
        path.rmdir()
    else:
        path.unlink()


def save(snap: Path, keep: Path) -> None:
    """Copy a good snapshot onto the claim and point `last-good` at it.

    Args:
        snap: The snapshot directory a build has just published.
        keep: The directory on the claim (the cache directory) that holds the copies.

    """
    keep.mkdir(parents=True, exist_ok=True)
    copy = keep / f"{LAST}-{os.getpid()}-{snap.name}"
    _remove(copy)
    _copy(snap, copy)
    link = keep / f".{LAST}-{os.getpid()}"
    link.unlink(missing_ok=True)
    link.symlink_to(copy.name)
    link.replace(keep / LAST)
    older = [p for p in keep.glob(f"{LAST}-*") if p.is_dir() and p != copy]
    for old in sorted(older, key=_age)[: max(len(older) + 1 - KEEP, 0)]:
        _remove(old)


def restore(base: Path, keep: Path) -> bool:
    """Serve the last good snapshot when this pod has published none.

    Args:
        base: The publish directory (/srv), whose `current` the server container serves.
        keep: The directory on the claim that save writes.

    Returns:
        True when it restored one; False when `current` already exists or there is nothing kept.

    """
    kept = keep / LAST
    if (base / "current").exists() or not kept.is_dir():
        return False
    # named to sort before every real snapshot, so the pruning of oldest-first drops it first
    dst = base / f"snap-0-restored-{os.getpid()}"
    _remove(dst)
    _copy(kept, dst)
    link = base / f".current-{os.getpid()}"
    link.unlink(missing_ok=True)
    link.symlink_to(dst.name)
    link.replace(base / "current")
    return True
