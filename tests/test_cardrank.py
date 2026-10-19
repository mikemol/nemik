# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W713: the plain-edge downstream weight equals the rdflib one on a fixture fleet."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.cardrank import downstream_weight
from nemik.rank import Weights, ref_of, successors
from nemik.rank import downstream_weight as graph_weight

LOCAL, PEER, PEER_BLOCKED = 5, 3, 2
CYCLE_LEN = 2
WEIGHTS = Weights(local=LOCAL, peer=PEER, peer_blocked=PEER_BLOCKED, operator=0)


def _card(
    symbol: str, status: str, enables: list[str], waits: list[str]
) -> dict[str, object]:
    """Build one queue entry.

    Args:
        symbol: Its symbol.
        status: Its state.
        enables: The cards it enables.
        waits: The cards it is blocked on.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": enables,
        "blocked_on": waits,
        "blocked_kind": "agent" if waits else None,
    }


def _fleet(root: Path) -> Graph:
    """Two repos with local and cross-repo edges, a done card and a blocked peer.

    Args:
        root: A scratch directory.

    Returns:
        The merged graph.

    """
    queues: dict[str, list[dict[str, object]]] = {
        "alpha": [
            _card("W1", "ready", ["W2", "beta:W5"], []),
            _card("W2", "ready", ["W3", "W4"], []),
            _card("W3", "done", ["W4"], []),
            _card("W4", "blocked", [], ["W2"]),
        ],
        "beta": [
            _card("W5", "blocked", ["W6"], ["alpha:W1"]),
            _card("W6", "ready", [], []),
        ],
    }
    merged = Graph()
    known = frozenset(queues)
    for repo, cards in queues.items():
        path = root / f"{repo}.json"
        body: dict[str, object] = {
            "version": 1,
            "counter": 9,
            "project_root": f"/fixture/{repo}",
            "residue": [],
            "waypoints": cards,
        }
        path.write_text(json.dumps(body))
        merged += queue_graph(repo, path, known)
    return merged


def test_every_card_weighs_the_same_both_ways(tmp_path: Path) -> None:
    """For each card in the fleet the plain-edge weight equals the graph weight."""
    g = _fleet(tmp_path)
    nodes = sorted(set(g.subjects(OSLC_CM.state, None)), key=str)
    succ = {ref_of(n): sorted(ref_of(s) for s in successors(g, n)) for n in nodes}
    done = {ref_of(n) for n in nodes if (n, OSLC_CM.state, NEMIK.Done) in g}
    blocked = {ref_of(n) for n in nodes if (n, OSLC_CM.state, NEMIK.Blocked) in g}
    weights = (LOCAL, PEER, PEER_BLOCKED)
    assert nodes
    for n in nodes:
        plain = downstream_weight(succ, done, blocked, ref_of(n), weights)
        assert plain == graph_weight(g, n, WEIGHTS)


def test_a_card_with_nothing_downstream_weighs_nothing() -> None:
    """A card nothing waits on has no weight."""
    assert downstream_weight({"a:W1": []}, set(), set(), "a:W1", (1, 1, 1)) == 0


def test_a_done_card_is_not_traversed() -> None:
    """Weight stops at a done card, and a cycle ends on the visited set."""
    succ = {"a:W1": ["a:W2"], "a:W2": ["a:W3"], "a:W3": ["a:W1"]}
    assert downstream_weight(succ, {"a:W2"}, set(), "a:W1", (1, 0, 0)) == 0
    assert downstream_weight(succ, set(), set(), "a:W1", (1, 0, 0)) == CYCLE_LEN
