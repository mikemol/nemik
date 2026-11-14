# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2198: serve's per-card effort and last activity, from the ledger rows and from the view.

The published view (`Model.doc`) reads each card's effort and last activity from the Activity
triples; `adapter.activity_by_card` finds them from the plain rows `ledger_rows` gives. They must
agree on the same ledger, so a consumer can move from the triples to the rows.
"""

import json
from typing import TYPE_CHECKING

from nemik.adapter import activity_by_card, ledger_rows, waypoint_uri
from nemik.serve import Model

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = (
    '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "one"\n'
    '2026-10-06T10:00:00Z  tick  W1  advanced  unblock  "two"\n'
    '2026-10-06T11:00:00Z  tick  W2  blocked   sweep    "three"\n'
    '2026-10-12T09:00:00Z  tick  -   advanced  sweep    "names no card"\n'
    '2026-10-13T09:00:00Z  peer  W1  advanced  msg      "a peer asked"\n'
)


def _root(tmp_path: Path) -> tuple[Path, Path]:
    """Write one repo's queue and ledger under a root.

    Returns:
        (the root, the ledger file).

    """
    claude = tmp_path / "a" / ".claude"
    claude.mkdir(parents=True)
    cards = [
        {
            "symbol": f"W{n}",
            "title": "t",
            "status": "ready",
            "blocked_on": [],
            "enables": [],
            "evidence": "",
        }
        for n in (1, 2)
    ]
    state = {
        "version": 1,
        "project_root": str(tmp_path / "a"),
        "counter": 2,
        "residue": [],
        "waypoints": cards,
    }
    (claude / "paths-forward.json").write_text(json.dumps(state), encoding="utf-8")
    ledger = claude / "paths-forward.ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    return tmp_path, ledger


def test_the_rows_give_the_effort_and_last_activity_the_view_publishes(tmp_path: Path) -> None:
    """Per card, the count by class and the latest stamp equal what the view reads off triples."""
    root, ledger = _root(tmp_path)
    model = Model(root)
    model.refresh()
    effort, last = activity_by_card("a", ledger_rows(ledger))
    published = {
        str(waypoint_uri("a", str(n["symbol"]))): (n["effort"], n["last_activity"])
        for n in model.doc["nodes"]
        if n["repo"] == "a"
    }
    assert published
    for card, (counts, stamp) in published.items():
        assert counts == effort.get(card, {})
        assert stamp == last.get(card, "")
    assert set(effort) == {str(waypoint_uri("a", "W1")), str(waypoint_uri("a", "W2"))}


def test_a_line_that_names_no_card_adds_nothing(tmp_path: Path) -> None:
    """MUTANT: counting the card-less line would give five lines on cards plus one."""
    _, ledger = _root(tmp_path)
    effort, _ = activity_by_card("a", ledger_rows(ledger))
    on_cards = sum(1 for line in LEDGER.splitlines() if "  -   " not in line)
    assert sum(sum(counts.values()) for counts in effort.values()) == on_cards
