# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W607: the warrant debt is a gauge per repo, zero when clean, counting only open claims."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.metrics import warrant_lines

CLAIM = "2026-10-13 operator ruling: demand is salience"


def _card(symbol: str, status: str, evidence: str) -> dict[str, object]:
    """Build one waypoint.

    Args:
        symbol: The card's symbol.
        status: Its status.
        evidence: Its evidence text.

    Returns:
        The queue row.

    """
    return {
        "symbol": symbol,
        "title": symbol,
        "status": status,
        "evidence": evidence,
        "next_bounded_step": "x",
    }


def _graph(tmp_path: Path, cards: list[dict[str, object]]) -> Graph:
    """Read a queue of the given cards.

    Args:
        tmp_path: A scratch directory.
        cards: The waypoints.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/life",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("life", path)


def test_the_debt_counts_open_unwarranted_claims_and_zero_is_a_value(
    tmp_path: Path,
) -> None:
    """Two open claims count; a done claim and a plain card do not; a clean repo reads 0."""
    cards = [
        _card("W1", "ready", CLAIM),
        _card("W2", "blocked", CLAIM),
        _card("W3", "done", CLAIM),
        _card("W4", "ready", "measured"),
    ]
    lines = warrant_lines(_graph(tmp_path, cards))
    assert lines == [
        "# TYPE nemik_warrant_debt gauge",
        'nemik_warrant_debt{repo="life"} 2',
    ]
    clean = warrant_lines(_graph(tmp_path, cards[3:]))
    assert clean[1:] == ['nemik_warrant_debt{repo="life"} 0']
