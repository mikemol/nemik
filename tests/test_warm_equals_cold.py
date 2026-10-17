# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W625: after any single-queue edit a warm survey equals a cold one.

The incremental SHACL cache re-judges a bounded neighbourhood of what changed
(nemik.shaclinc.HOPS). A shape that reads further than that would serve a stale verdict silently,
so this runs a fixed sequence of edits (a card closed, reopened, dropped, or given an edge) and
holds each warm result to a cold full run of an identical copy of the tree. A deeper shape fails
here. The sequence is a table of numbers taken modulo the queue's size, so it is the same every run.
"""

import json
import shutil
from pathlib import Path

import pytest

from nemik import cachestore
from nemik.check import survey

FLEET = Path(__file__).parent / "fixtures" / "fleet"
KINDS = ["close", "reopen", "drop", "edge"]
# (queue, card, kind, target card for an edge), each taken modulo what the tree holds
TABLE = [(3, 7, 0, 2), (11, 1, 3, 5), (6, 4, 2, 0), (14, 9, 1, 8), (2, 13, 3, 1)]

Queue = dict[str, list[dict[str, object]]]


def _verdicts(root: Path) -> list[tuple[str, str, str, str]]:
    """Collect every finding a survey of the root reports.

    Args:
        root: The fleet root.

    Returns:
        (repo, severity, symbol, message) rows, sorted.

    """
    return sorted(
        (repo, sev, sym, msg)
        for repo, _, found in survey(root)
        for sev, sym, msg in found
    )


def _edit(fleet: Path, row: tuple[int, int, int, int]) -> str:
    """Apply one edit from the table to one repo's queue.

    Args:
        fleet: The copied fleet root.
        row: (queue, card, kind, target), each taken modulo what exists.

    Returns:
        What was done, for the failure message.

    """
    found = fleet.glob("*/paths-forward.json")
    queues = sorted(p for p in found if p.parent.name[0] != ".")
    path = queues[row[0] % len(queues)]
    state: Queue = json.loads(path.read_text(encoding="utf-8"))
    cards = state["waypoints"]
    card = cards[row[1] % len(cards)]
    kind = KINDS[row[2] % len(KINDS)]
    if kind == "close":
        card["status"] = "done"
    elif kind == "reopen":
        card["status"] = "ready"
    elif kind == "drop" and len(cards) > 1:
        cards.remove(card)
    else:
        card["enables"] = [str(cards[row[3] % len(cards)]["symbol"])]
    path.write_text(json.dumps(state), encoding="utf-8")
    return f"{kind} {card['symbol']} in {path.parent.name}"


def test_a_warm_survey_equals_a_cold_one_after_each_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Five edits in a row: the warm result must match a cold twin every time."""
    fleet = tmp_path / "fleet"
    shutil.copytree(FLEET, fleet)
    monkeypatch.setenv("NEMIK_ROOT", str(fleet))
    monkeypatch.setenv("NEMIK_CACHE_DIR", str(tmp_path / "cache"))
    cachestore.RESTORED[0] = False
    _verdicts(fleet)
    for step, row in enumerate(TABLE):
        done = _edit(fleet, row)
        warm = _verdicts(fleet)
        twin = tmp_path / f"twin{step}"
        shutil.copytree(fleet, twin)
        assert warm == _verdicts(twin), f"stale after: {done}"
