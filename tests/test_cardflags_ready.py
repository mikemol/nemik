# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W714: the plain-edge ready-behind-open flag equals blocks.ready_behind_open."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import ready_behind_open as graph_flag
from nemik.cardflags import ready_behind_open
from nemik.rank import ref_of


def _card(symbol: str, status: str, enables: list[str]) -> dict[str, object]:
    """Build one queue entry.

    Args:
        symbol: Its symbol.
        status: Its state.
        enables: The cards it enables.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": enables,
        "blocked_on": [],
        "blocked_kind": None,
    }


def _fleet(root: Path) -> Graph:
    """Two repos: a ready card behind one open card, an umbrella, a done enabler, a peer enabler.

    Args:
        root: A scratch directory.

    Returns:
        The merged graph.

    """
    queues: dict[str, list[dict[str, object]]] = {
        "alpha": [
            _card("W1", "ready", ["W2"]),
            _card("W2", "ready", []),
            _card("W3", "ready", ["W5"]),
            _card("W4", "ready", ["W5"]),
            _card("W5", "ready", []),
            _card("W6", "done", ["W7"]),
            _card("W7", "ready", []),
            _card("W8", "ready", []),
        ],
        "beta": [_card("W9", "working", ["alpha:W8"])],
    }
    merged = Graph()
    known = frozenset(queues)
    for repo, cards in queues.items():
        body: dict[str, object] = {
            "version": 1,
            "counter": 9,
            "project_root": f"/fixture/{repo}",
            "residue": [],
            "waypoints": cards,
        }
        path = root / f"{repo}.json"
        path.write_text(json.dumps(body))
        merged += queue_graph(repo, path, known)
    return merged


def test_the_plain_flag_matches_the_graph_reading(tmp_path: Path) -> None:
    """Same cards, same enablers: W2 and the peer-enabled W8, not the umbrella W5 or W7."""
    g = _fleet(tmp_path)
    nodes = set(g.subjects(OSLC_CM.state, None))
    enablers = {
        ref_of(n): [ref_of(c) for c in g.subjects(NEMIK.enables, n)] for n in nodes
    }
    ready = {ref_of(n) for n in g.subjects(OSLC_CM.state, NEMIK.Ready)}
    open_cards = {ref_of(n) for n in nodes if (n, OSLC_CM.state, NEMIK.Done) not in g}
    plain = ready_behind_open(enablers, ready, open_cards)
    reference = {
        ref_of(n): sorted(ref_of(c) for c in cs) for n, cs in graph_flag(g).items()
    }
    assert plain == reference
    assert sorted(plain) == ["alpha:W2", "alpha:W8"]


def test_no_enablers_flags_nothing() -> None:
    """A ready card nothing enables is not behind anything."""
    assert not ready_behind_open({}, {"a:W1"}, {"a:W1"})
