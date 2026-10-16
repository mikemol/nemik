# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W531: the graph nemik serves as Turtle or N-Triples parses back to the same graph."""

import json
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic

from nemik.adapter import queue_graph


def _graph(tmp_path: Path) -> Graph:
    """Read a queue whose cards exercise the term kinds the adapter emits.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {
            "symbol": "W1",
            "title": 'quotes " and unicode é and a newline\nin a title',
            "status": "ready",
            "issued_at": "2026-10-16T14:02:11Z",
            "touches": ["rank", "file:src/x.py!w"],
            "enables": ["W2"],
            "next_bounded_step": "edit src/nemik/x.py",
        },
        {"symbol": "W2", "title": "b", "status": "blocked", "blocked_on": ["W1"]},
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/nemik",
        "counter": 2,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("nemik", path)


def test_the_served_forms_parse_back_to_the_same_graph(tmp_path: Path) -> None:
    """Turtle (/graph.ttl) and N-Triples (the static view) both round-trip, term for term."""
    original = _graph(tmp_path)
    assert len(original) > 0
    for form in ("turtle", "nt"):
        text = original.serialize(format=form)
        again = Graph().parse(data=text, format=form)
        assert isomorphic(original, again), form
