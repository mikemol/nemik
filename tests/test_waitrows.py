# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W875, W883: the graph's cross-repo wait edges become waitseries rows."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.rank import Weights
from nemik.waitrows import UNRANKED, blocker_positions, wait_edges, wait_rows
from nemik.waitseries import samples

EXCLUDED_AGES = {3, 4, 5, 9}
W5_TICKS, W6_TICKS, W11_TICKS = 7, 2, 6
W = Weights(local=1, peer=2, peer_blocked=8, operator=0)


def _card(
    symbol: str, status: str, waits: list[str], ticks: int = 0
) -> dict[str, object]:
    """Build one queue entry.

    Args:
        symbol: Its symbol.
        status: Its state.
        waits: The cards or asks it is blocked on.
        ticks: How many loop ticks it has been blocked.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": [],
        "blocked_on": waits,
        "blocked_kind": "agent" if waits else None,
        "ticks_blocked": ticks,
    }


def _fleet(root: Path) -> Graph:
    """Two repos: alpha's cards, and beta's cards waiting on them in every way a card can.

    Args:
        root: A scratch directory.

    Returns:
        The merged graph.

    """
    queues: dict[str, list[dict[str, object]]] = {
        "alpha": [
            _card("W1", "ready", []),
            _card("W2", "blocked", ["W1"], ticks=3),
            _card("W3", "ready", []),
        ],
        "beta": [
            _card("W5", "blocked", ["alpha:W1"], ticks=7),
            _card("W6", "blocked", ["alpha:W1", "alpha:W3"], ticks=2),
            _card("W7", "ready", []),
            _card("W8", "blocked", ["gamma"], ticks=5),
            _card("W9", "blocked", ["operator: decide something"], ticks=4),
            _card("W10", "done", ["alpha:W1"], ticks=9),
            _card("W11", "blocked", ["alpha:W2"], ticks=6),
        ],
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
        path.write_text(json.dumps(body))
        merged += queue_graph(repo, path, known)
    return merged


def test_a_blocked_card_waiting_on_another_repos_card_is_a_row(tmp_path: Path) -> None:
    """W5 waits 7 ticks, W6 on two alpha cards 2 each, W11 on alpha:W2 for 6."""
    rows = wait_rows(_fleet(tmp_path))
    assert sorted(rows) == [
        ("beta", "alpha", 2),
        ("beta", "alpha", 2),
        ("beta", "alpha", 6),
        ("beta", "alpha", 7),
    ]


def test_local_waits_workstreams_asks_and_done_cards_are_not_rows(
    tmp_path: Path,
) -> None:
    """alpha:W2 waits inside its repo, W8 on a workstream, W9 on the operator, W10 is done."""
    rows = wait_rows(_fleet(tmp_path))
    assert all(
        waiting == "beta" and blocking == "alpha" for waiting, blocking, _ in rows
    )
    assert not EXCLUDED_AGES & {ticks for _, _, ticks in rows}


def test_the_rows_group_into_one_sample_per_pair_of_repos(tmp_path: Path) -> None:
    """Slice 1's samples() over these rows: one beta-to-alpha pair, oldest 7, four waiting."""
    (sample,) = samples(wait_rows(_fleet(tmp_path)))
    assert (sample.waiter, sample.blocker, sample.oldest, sample.count) == (
        "beta",
        "alpha",
        7,
        4,
    )


def test_ready_cards_are_ranked_from_one_and_other_cards_are_not(
    tmp_path: Path,
) -> None:
    """Every ready card has its own place in the fleet order; a blocked card has none."""
    place = blocker_positions(_fleet(tmp_path), W)
    assert {"alpha:W1", "alpha:W3", "beta:W7"} <= set(place)
    assert sorted(place.values()) == list(range(1, len(place) + 1))
    assert "alpha:W2" not in place
    assert "beta:W5" not in place


def test_each_edge_carries_the_rank_position_of_its_blocker(tmp_path: Path) -> None:
    """W5's blocker is alpha:W1; W6's are alpha:W1 and alpha:W3; W11's blocker is not ranked."""
    g = _fleet(tmp_path)
    place = blocker_positions(g, W)
    edges = wait_edges(g, W)
    assert sorted(position for _, _, ticks, position in edges if ticks == W5_TICKS) == [
        place["alpha:W1"]
    ]
    assert sorted(
        position for _, _, ticks, position in edges if ticks == W6_TICKS
    ) == sorted([place["alpha:W1"], place["alpha:W3"]])
    assert [position for _, _, ticks, position in edges if ticks == W11_TICKS] == [
        UNRANKED
    ]
    assert UNRANKED not in place.values()
