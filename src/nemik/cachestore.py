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
from typing import TYPE_CHECKING

from nemik import flow, shaclinc

if TYPE_CHECKING:
    from pathlib import Path

FORMAT = 1
NAME = "build-caches.pickle"
WATCHED = ("data/shapes.ttl", "shaclinc.py", "flow.py", "cachestore.py")


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


def save(directory: Path) -> int:
    """Write both caches under `directory` atomically; returns the bytes written."""
    directory.mkdir(parents=True, exist_ok=True)
    blob = {
        "stamp": stamp(),
        "shaclinc": shaclinc.export_cache(),
        "flow": flow.export_solves(),
    }
    body = pickle.dumps(blob, protocol=pickle.HIGHEST_PROTOCOL)
    tmp = directory / f".{NAME}.{os.getpid()}"
    tmp.write_bytes(body)
    os.replace(tmp, directory / NAME)
    return len(body)


def load(directory: Path) -> bool:
    """Restore both caches from `directory`; False (a cold start) for anything that is not this code's."""
    try:
        blob = pickle.loads((directory / NAME).read_bytes())
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
