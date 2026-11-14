# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1099: the operator asks' last activity, from the Activity triples and from the summary.

`blocks.operator_asks` reads each waiting card's last activity off the graph's Activity triples;
given the per-card summary (`adapter.activity_by_card`) it reads that instead. The rows must be
equal, so the triples can stop being built.
"""

import json
from typing import TYPE_CHECKING

from nemik.adapter import activity_by_card, ledger_graph, ledger_rows, queue_graph
from nemik.blocks import operator_asks

if TYPE_CHECKING:
    from pathlib import Path

    from rdflib import Graph

LEDGER = (
    '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "one"\n'
    '2026-10-06T10:00:00Z  tick  W1  advanced  unblock  "two"\n'
    '2026-10-12T09:00:00Z  tick  W2  advanced  sweep    "other"\n'
)


def _graph(tmp_path: Path) -> tuple[Graph, Path]:
    """Build a repo graph: one card waiting on the operator, one that is not, and a ledger.

    Returns:
        (the merged queue and ledger graph, the ledger file).

    """
    cards = [
        {
            "symbol": "W1",
            "title": "t",
            "status": "blocked",
            "blocked_on": ["operator: decide which option"],
            "blocked_kind": "human",
            "enables": [],
            "evidence": "",
        },
        {
            "symbol": "W2",
            "title": "u",
            "status": "ready",
            "blocked_on": [],
            "enables": [],
            "evidence": "",
        },
    ]
    state = {
        "version": 1,
        "project_root": str(tmp_path),
        "counter": 2,
        "residue": [],
        "waypoints": cards,
    }
    queue = tmp_path / "paths-forward.json"
    queue.write_text(json.dumps(state), encoding="utf-8")
    ledger = tmp_path / "paths-forward.ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    g = queue_graph("a", queue)
    g += ledger_graph("a", ledger)[0]
    return g, ledger


def test_the_summary_gives_the_asks_the_last_activity_the_triples_give(tmp_path: Path) -> None:
    """The waiting card's last_activity is the same on both routes, and is not empty."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    g, ledger = _graph(first)
    from_triples = operator_asks(g)
    other, _ = _graph(second)
    _, last = activity_by_card("a", ledger_rows(ledger))
    from_summary = operator_asks(other, last)
    assert len(from_triples) == 1
    assert from_triples[0]["last_activity"].startswith("2026-10-06T10:00:00")
    assert from_summary == from_triples
