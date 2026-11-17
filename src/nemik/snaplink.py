# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2063: a snapshot shares the bytes of the files it did not change with the one before it.

The pod's snapshots live in an emptyDir with a size limit (512Mi), and the builder holds the new
snapshot beside the last `keep` ones while it publishes: four to five copies of a view that is about
102 MiB (the kubelet's own reading, 157 inodes a snapshot), so the peak is within 2 MiB of the
limit and has no room for the queues' growth. Consecutive snapshots are mostly the same bytes. A
file whose bytes equal the same path's in the previous snapshot becomes a hard link to it, and the
volume's accounting counts an inode once, so the peak falls to one full snapshot plus what changed.
A snapshot is never written to after it is built, so a shared inode is never changed under a reader.

Only os and pathlib, so the Codon census compiles it.
"""

import os

from nemik._typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _shareable(item: Path, twin: Path) -> bool:
    """Say whether `item` can become a link to `twin`: a distinct regular file with the same bytes.

    Returns:
        True when both are regular files that do not already share an inode, their sizes match and
        so do their bytes.

    """
    if not twin.is_file() or twin.is_symlink() or item.samefile(twin):
        return False
    if item.stat().st_size != twin.stat().st_size:
        return False
    return item.read_bytes() == twin.read_bytes()


def link_unchanged(snap: Path, before: Path) -> int:
    """Replace each file of `snap` that `before` holds unchanged with a hard link to it.

    Args:
        snap: The snapshot just built.
        before: The previous snapshot (the directory `current` pointed at).

    Returns:
        How many files were linked. A symlink, a directory and a file `before` lacks or holds
        different bytes for are left as built; a file already sharing an inode is not counted.

    """
    linked = 0
    for item in snap.iterdir():
        twin = before / item.name
        if item.is_symlink():
            continue
        if item.is_dir():
            if twin.is_dir() and not twin.is_symlink():
                linked += link_unchanged(item, twin)
        elif _shareable(item, twin):
            item.unlink()
            os.link(twin, item)
            linked += 1
    return linked
