# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W547: a done card's cross-repo edges, walked over three repos' queues."""

import json

from nemik.workrows import cross_repo, edges_of

ALPHA: dict[str, list[dict[str, object]]] = {
    "waypoints": [{"symbol": "W1", "enables": ["beta:W5", "W2", "alpha:W3"]}]
}
BETA: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W5", "blocked_on": ["alpha:W1"], "caused_by": "alpha:W1"},
        {"symbol": "W6", "blocked_on": ["alpha:W9"]},
    ]
}
GAMMA: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W2", "caused_by": "alpha:W1"},
        {"symbol": "W3", "blocked_on": ["W1"]},
    ]
}
QUEUES = {
    "alpha": json.dumps(ALPHA),
    "beta": json.dumps(BETA),
    "gamma": json.dumps(GAMMA),
}


def test_a_cards_edges_cover_all_three_kinds_across_repos() -> None:
    """beta:W5 waits on it and was caused by it; gamma:W2 was caused by it; it enables beta:W5."""
    assert edges_of(QUEUES, "alpha", "W1") == [
        ("blocked_on", "beta", "W5"),
        ("caused_by", "beta", "W5"),
        ("caused_by", "gamma", "W2"),
        ("enables", "beta", "W5"),
    ]


def test_edges_inside_the_cards_own_repo_are_left_out() -> None:
    """W2 and alpha:W3 in alpha's own enables are alpha's business; gamma's bare W1 is gamma's."""
    kinds = {(kind, repo) for kind, repo, _ in edges_of(QUEUES, "alpha", "W1")}
    assert ("enables", "alpha") not in kinds
    assert ("blocked_on", "gamma") not in kinds


def test_a_card_nobody_names_has_no_edges() -> None:
    """Another card's symbol, and a repo with no queue, give nothing."""
    assert edges_of(QUEUES, "beta", "W6") == []
    assert edges_of(QUEUES, "delta", "W1") == []


def test_cross_repo_reads_the_prefix() -> None:
    """A bare symbol and the repo's own prefix are local."""
    assert cross_repo("beta:W5", "alpha")
    assert not cross_repo("alpha:W3", "alpha")
    assert not cross_repo("W2", "alpha")
