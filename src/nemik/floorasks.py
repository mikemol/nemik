# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Witness that summit floor asks point at live waypoints (nemik:W42).

Each `summit/floor/*.bib` entry may carry `waypoint = {<repo>:W<n>}`. The pointer must resolve to
a waypoint in that repo's queue that is not dropped; otherwise the ask cites nothing an agent owns.
"""

import json
import re
from pathlib import Path

from nemik.queuefiles import QUEUE, workstream_files
from nemik.tomlview import table, tables

# Same field regex as summit's scripts/place_intake.py (`waypoint` is a real top-level field).
_WAYPOINT = re.compile(r"^\s*waypoint\s*=\s*\{([^}]*)\}", re.MULTILINE)
_KEY = re.compile(r"^@\w+\{([^,\s]+),", re.MULTILINE)
_ENTRY = re.compile(r"^@\w+\{.*?^\}", re.MULTILINE | re.DOTALL)


def floor_asks(floor: Path) -> list[tuple[str, str]]:
    """(bib key, waypoint pointer) for every floor entry carrying a waypoint field.

    Returns:
        The (bib key, waypoint pointer) pairs, key `?` when the entry has none.

    """
    out: list[tuple[str, str]] = []
    for bib in sorted(floor.glob("*.bib")):
        text = bib.read_text(encoding="utf-8", errors="replace")
        blocks: list[str] = _ENTRY.findall(text)
        for block in blocks:
            wp, key = _WAYPOINT.search(block), _KEY.search(block)
            if wp:
                name = "?"
                if key:
                    name = key.group(1)
                pointer: str = wp.group(1)
                out.append((name, pointer.strip()))
    return out


def _statuses(path: Path) -> dict[str, str]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    data = table(raw)
    st = {
        str(w["symbol"]): str(w.get("status", ""))
        for w in tables(data.get("waypoints"))
    }
    st.update({str(r["symbol"]): "dropped" for r in tables(data.get("residue"))})
    return st


def unresolved(root: Path, floor: Path) -> list[tuple[str, str, str]]:
    """(key, pointer, why) for each ask whose waypoint is malformed, unknown, or dropped.

    Returns:
        The (key, pointer, reason) triples of the asks that do not resolve.

    """
    queues = dict(workstream_files(root, QUEUE))
    cache: dict[str, dict[str, str]] = {}
    bad = []
    for key, ptr in floor_asks(floor):
        repo, _, sym = ptr.partition(":")
        if not re.fullmatch(r"W\d+", sym):
            bad.append((key, ptr, "malformed"))
            continue
        if repo not in queues:
            bad.append((key, ptr, "no queue for repo"))
            continue
        st = cache.setdefault(repo, _statuses(queues[repo])).get(sym)
        if st is None:
            bad.append((key, ptr, "no such waypoint"))
        elif st == "dropped":
            bad.append((key, ptr, "dropped"))
    return bad
