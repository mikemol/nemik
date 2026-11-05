# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W518: the build's two caches, kept between short-lived processes.

The long-lived server rebuilt in about 16 s CPU because it kept the last SHACL run (nemik:W400:
only what changed is validated again) and the flow solves (nemik:W401). A publisher that starts a
fresh process for every build (nemik:W503) lost both: 37-57 s CPU cold, more than a minute of one
core. This writes them beside the snapshots after a build and reads them before the next, so each
build costs about the warm figure and its memory still goes back to the OS when the process exits.

A cache is only as good as what computed it, so the file carries a stamp over the shapes, the code
that reads them and the engines' versions; a stamp that differs, or any file that will not load,
is a cold start, never an error. The file is JSON (nemik:W1642): each distinct RDF term is stored
once, as its n3 text, and the triples and results name terms by index; Fractions, tuples and the
flow solves are tagged lists. Nothing here executes what it reads.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path
from typing import cast

from rdflib.term import Node
from rdflib.util import from_n3

from nemik import flow, shaclinc

FORMAT = 2
NAME = "build-caches.json"
WATCHED = (
    "data/shapes.ttl",
    "shaclinc.py",
    "shapedepth.py",
    "flow.py",
    "cachestore.py",
)
KEEP = 4  # per-build files kept in the user directory
STRAY = 3600  # seconds before a temp file a killed run left behind is swept


def stamp() -> str:
    """Stamp what the cached values were computed by: the shapes, the cache code, the engines.

    Returns:
        The SHA-256 hex digest of the format, the watched files and the engine versions.

    """
    digest = hashlib.sha256(f"format {FORMAT}".encode())
    for name in WATCHED:
        digest.update(files("nemik").joinpath(name).read_bytes())
    for dist in ("pyshacl", "rdflib"):
        try:
            digest.update(f"{dist} {version(dist)}".encode())
        except PackageNotFoundError:
            digest.update(f"{dist} none".encode())
    return digest.hexdigest()


def content_key(parts: list[bytes]) -> str:
    """Name a set of inputs by their content (nemik:W763).

    Each part is length-prefixed, so two lists that join to the same bytes still differ.

    Returns:
        The SHA-256 of the parts, in hex.

    """
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


class Terms:
    """The distinct RDF terms of one cache file, each stored once as its n3 text."""

    def __init__(self) -> None:
        """Start with no terms."""
        self.index: dict[Node, int] = {}
        self.table: list[str] = []

    def add(self, term: Node) -> int:
        """Give `term` its place in the table, adding it the first time it is seen.

        Returns:
            The term's index.

        """
        found = self.index.get(term)
        if found is None:
            found = len(self.table)
            self.index[term] = found
            self.table.append(term.n3())
        return found


def _held_json(held: shaclinc.Held, terms: Terms) -> object:
    """Write the SHACL runs with their terms as indexes.

    Returns:
        A JSON-able dict from each run's key to its triples and results.

    """
    runs: dict[str, object] = {}
    for key, (triples, results) in held.items():
        runs[key] = {
            "triples": [
                [terms.add(s), terms.add(p), terms.add(o)] for s, p, o in triples
            ],
            "results": [
                [terms.add(focus), [[sev, msg] for sev, msg in rows]]
                for focus, rows in results.items()
            ],
        }
    return runs


def _solves_json(value: object) -> object:
    """Tag a flow value for JSON: Fractions, tuples, dicts and Flow solves keep their shape.

    Returns:
        A JSON-able value that _solves_value turns back into the same object.

    """
    if isinstance(value, Fraction):
        return ["F", value.numerator, value.denominator]
    if isinstance(value, flow.Flow):
        return [
            "W",
            _solves_json(value.salience),
            _solves_json(value.fibre),
            _solves_json(value.stranded),
            _solves_json(value.potential),
            _solves_json(value.current),
        ]
    if isinstance(value, tuple):
        return ["T", [_solves_json(v) for v in value]]
    if isinstance(value, dict):
        return ["D", [[_solves_json(k), _solves_json(v)] for k, v in value.items()]]
    return value


def save(directory: Path, name: str = NAME) -> int:
    """Write both caches under `directory` atomically; returns the bytes written.

    Returns:
        The number of bytes written.

    """
    directory.mkdir(parents=True, exist_ok=True)
    terms = Terms()
    held = _held_json(shaclinc.export_cache(), terms)
    blob: dict[str, object] = {
        "stamp": stamp(),
        "shaclinc": held,
        "flow": _solves_json(flow.export_solves()),
        "terms": terms.table,
    }
    body = json.dumps(blob, separators=(",", ":")).encode()
    tmp = directory / f".{name}.{os.getpid()}"
    tmp.write_bytes(body)
    Path(tmp).replace(directory / name)
    return len(body)


def _term(text: str) -> Node:
    """Read one term back from its n3 text.

    Returns:
        The term.

    Raises:
        TypeError: the text is not an RDF term (load treats it as a cold start).

    """
    got = from_n3(text)
    if not isinstance(got, Node):
        msg = f"not an RDF term: {text}"
        raise TypeError(msg)
    return got


def _held_value(raw: object, table: list[Node]) -> shaclinc.Held:
    """Read the SHACL runs back, looking each term up by its index.

    Returns:
        The runs as shaclinc holds them.

    """
    held: shaclinc.Held = {}
    for key, run in cast("dict[str, object]", raw).items():
        body = cast("dict[str, object]", run)
        triples = frozenset(
            (table[s], table[p], table[o])
            for s, p, o in cast("list[list[int]]", body["triples"])
        )
        results = {
            table[cast("int", row[0])]: [
                (sev, msg) for sev, msg in cast("list[list[str]]", row[1])
            ]
            for row in cast("list[list[object]]", body["results"])
        }
        held[key] = (triples, results)
    return held


def _solves_value(raw: object) -> object:
    """Read a tagged flow value back into Fractions, tuples, dicts and Flow solves.

    Returns:
        The value _solves_json was given.

    """
    if not isinstance(raw, list):
        return raw
    items: list[object] = raw
    tag = items[0]
    if tag == "F":
        return Fraction(cast("int", items[1]), cast("int", items[2]))
    if tag == "T":
        return tuple(_solves_value(v) for v in cast("list[object]", items[1]))
    if tag == "D":
        pairs = cast("list[list[object]]", items[1])
        return {_solves_value(k): _solves_value(v) for k, v in pairs}
    return flow.Flow(
        salience=cast("dict[str, Fraction]", _solves_value(items[1])),
        fibre=cast("dict[str, dict[str, Fraction]]", _solves_value(items[2])),
        stranded=cast("dict[str, Fraction]", _solves_value(items[3])),
        potential=cast("dict[str, Fraction]", _solves_value(items[4])),
        current=cast("dict[tuple[str, str], Fraction]", _solves_value(items[5])),
    )


def _blob(directory: Path, name: str) -> dict[str, object]:
    """Read the cache file as the JSON object it holds.

    Returns:
        The file's top-level object.

    """
    parsed: object = json.loads((directory / name).read_bytes())
    return cast("dict[str, object]", parsed)


def _decode(
    blob: dict[str, object],
) -> tuple[shaclinc.Held, dict[flow.SolveKey, flow.Flow]]:
    """Read both caches out of a blob whose stamp already matches.

    Returns:
        The SHACL runs and the flow solves.

    """
    table = [_term(text) for text in cast("list[str]", blob["terms"])]
    held = _held_value(blob["shaclinc"], table)
    return held, cast("dict[flow.SolveKey, flow.Flow]", _solves_value(blob["flow"]))


def load(directory: Path, name: str = NAME) -> bool:
    """Restore both caches from `directory`; False (a cold start) for anything not this code's.

    Returns:
        True when both caches were restored, False for a cold start.

    """
    try:
        blob = _blob(directory, name)
        if blob["stamp"] != stamp():
            return False
        held, solves = _decode(blob)
    except (OSError, KeyError, TypeError, ValueError, IndexError):
        return False
    shaclinc.import_cache(held)
    flow.import_solves(solves)
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
        build-caches-<first 16 hex of the stamp>.json.

    """
    return f"build-caches-{stamp()[:16]}.json"


def _age(path: Path) -> float:
    """Order key for prune.

    Args:
        path: A per-build cache file.

    Returns:
        When the file was last written.

    """
    return path.stat().st_mtime


def prune(directory: Path) -> None:
    """Remove the oldest per-build files beyond KEEP, and the pickles an older format left.

    An unreadable directory is ignored.

    Args:
        directory: The user cache directory.

    """
    try:
        found = sorted(
            directory.glob("build-caches-*.json"),
            key=_age,
            reverse=True,
        )
        strays = [
            p
            for p in directory.glob(".build-caches-*.json.*")
            if time.time() - _age(p) > STRAY
        ]
        legacy = list(directory.glob("build-caches*.pickle"))
    except OSError:
        return
    for old in [*found[KEEP:], *strays, *legacy]:
        try:
            old.unlink()
        except OSError:
            continue


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
