# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Tests for waitrows.oldest_waits: the longest-waiting card of each pair of repos (nemik:W886)."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.waitrows import oldest_waits

LONGEST = 7
SHORTER = 2


def _card(
    symbol: str, status: str, blocked_on: list[str], ticks: int
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": [],
        "touches": [],
        "blocked_on": blocked_on,
        "blocked_kind": "agent" if blocked_on else None,
        "next_bounded_step": "do it",
        "evidence": "",
        "issued_at": "2026-10-01T00:00:00Z",
        "last_worked": None,
        "ticks_blocked": ticks,
    }


def _fleet(root: Path) -> Graph:
    queues: dict[str, list[dict[str, object]]] = {
        "alpha": [_card("W1", "ready", [], 0), _card("W3", "ready", [], 0)],
        "beta": [
            _card("W5", "blocked", ["alpha:W1"], LONGEST),
            _card("W6", "blocked", ["alpha:W3"], SHORTER),
        ],
        "gamma": [_card("W9", "blocked", ["alpha:W3"], SHORTER)],
    }
    merged = Graph()
    known = frozenset(queues)
    for repo, cards in queues.items():
        path = root / f"{repo}.json"
        body: dict[str, object] = {
            "version": 1,
            "counter": 20,
            "project_root": f"/fixture/{repo}",
            "residue": [],
            "waypoints": cards,
        }
        path.write_text(json.dumps(body), encoding="utf-8")
        merged += queue_graph(repo, path, known)
    return merged


def test_each_pair_names_its_longest_waiting_card_and_its_blocker(
    tmp_path: Path,
) -> None:
    """Beta's longest wait is W5 on alpha:W1; gamma has one card, W9 on alpha:W3."""
    assert oldest_waits(_fleet(tmp_path)) == [
        ("beta", "alpha", LONGEST, "beta:W5", "alpha:W1"),
        ("gamma", "alpha", SHORTER, "gamma:W9", "alpha:W3"),
    ]
