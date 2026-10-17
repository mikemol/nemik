# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W518: the build's two caches, kept between short-lived processes.

The long-lived server rebuilt in about 16 s CPU because it kept the last SHACL run (nemik:W400: only
what changed is validated again) and the flow solves (nemik:W401). A publisher that starts a fresh
process for every build (nemik:W503) lost both: 37-57 s CPU cold, more than a minute of one core.
This writes them beside the snapshots after a build and reads them before the next, so each build
costs about the warm figure and its memory still goes back to the OS when the process exits.

A cache is only as good as what computed it, so the file carries a stamp over the shapes, the code that
reads them and the engines' versions; a stamp that differs, or any file that will not load, is a cold
start, never an error. The file is the publisher's own, in a directory it writes: nothing here reads a
pickle that came from anywhere else.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path

from nemik import flow, shaclinc

FORMAT = 1
NAME = "build-caches.pickle"
WATCHED = (
    "data/shapes.ttl",
    "shaclinc.py",
    "shapedepth.py",
    "flow.py",
    "cachestore.py",
)
KEEP = 4  # per-build files kept in the user directory


def stamp() -> str:
    """What the cached values were computed by: the shapes, the cache code, the engines."""
    digest = hashlib.sha256(f"format {FORMAT}".encode())
    for name in WATCHED:
        digest.update(files("nemik").joinpath(name).read_bytes())
    for dist in ("pyshacl", "rdflib"):
        try:
            digest.update(f"{dist} {version(dist)}".encode())
        except PackageNotFoundError:
            digest.update(f"{dist} none".encode())
    return digest.hexdigest()


def save(directory: Path, name: str = NAME) -> int:
    """Write both caches under `directory` atomically; returns the bytes written."""
    directory.mkdir(parents=True, exist_ok=True)
    blob = {
        "stamp": stamp(),
        "shaclinc": shaclinc.export_cache(),
        "flow": flow.export_solves(),
    }
    body = pickle.dumps(blob, protocol=pickle.HIGHEST_PROTOCOL)
    tmp = directory / f".{name}.{os.getpid()}"
    tmp.write_bytes(body)
    os.replace(tmp, directory / name)
    return len(body)


def load(directory: Path, name: str = NAME) -> bool:
    """Restore both caches from `directory`; False (a cold start) for anything that is not this code's."""
    try:
        blob = pickle.loads((directory / name).read_bytes())
        if blob["stamp"] != stamp():
            return False
        shaclinc.import_cache(blob["shaclinc"])
        flow.import_solves(blob["flow"])
    except (
        OSError,
        EOFError,
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        ImportError,
        IndexError,
        pickle.UnpicklingError,
    ):
        return False
    return True


RESTORED = [False]
USER_NAME = "nemik"


def user_dir() -> Path:
    """Name the per-user directory the readers keep the caches in (nemik:W625).

    Returns:
        $NEMIK_CACHE_DIR, else $XDG_CACHE_HOME/nemik, else ~/.cache/nemik.

    """
    named = os.environ.get("NEMIK_CACHE_DIR")
    if named:
        return Path(named)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / USER_NAME


def user_name() -> str:
    """Name this build's file in the user directory, so builds do not evict one another.

    A pushed build and a dev tree have different code bytes, so different stamps; with one shared
    file name each run of one overwrote the other's cache and both read cold (nemik:W630).

    Returns:
        build-caches-<first 16 hex of the stamp>.pickle.

    """
    return f"build-caches-{stamp()[:16]}.pickle"


def _age(path: Path) -> float:
    """Order key for prune.

    Args:
        path: A per-build cache file.

    Returns:
        When the file was last written.

    """
    return path.stat().st_mtime


def prune(directory: Path) -> None:
    """Remove the oldest per-build files beyond KEEP; an unreadable directory is ignored.

    Args:
        directory: The user cache directory.

    """
    try:
        found = sorted(
            directory.glob("build-caches-*.pickle"),
            key=_age,
            reverse=True,
        )
        for old in found[KEEP:]:
            old.unlink()
    except OSError:
        return


def restore_user() -> bool:
    """Restore the readers' caches once per process (nemik:W625).

    A cold fleet survey cost 142 s CPU, 133 s of it SHACL; with the caches of the last run loaded it
    cost 11 s. Every reader (nemik-check, -rank, -stackable, -metrics, the hooks) starts a fresh
    process, so without this each paid the cold figure.

    Returns:
        True when a cache from this code was loaded; False for a cold start.

    """
    if RESTORED[0]:
        return True
    RESTORED[0] = load(user_dir(), user_name())
    return RESTORED[0]


def persist_user() -> None:
    """Keep this process's caches for the next reader; an unwritable directory is ignored."""
    try:
        save(user_dir(), user_name())
    except OSError:
        return
    prune(user_dir())
