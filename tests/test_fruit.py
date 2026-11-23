# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W178: low-hanging fruit as one virtual row."""

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri, workstream_uri
from nemik.rank import RankOptions, RankRow, fruit, rank
from nemik.score import load_weights

TWO_MEMBERS_WEIGHT = 2
TAGGED_WEIGHT = 4
PILE_WEIGHT = 9
READY_PILE_WEIGHT = 8


def test_members_are_leaves_moving_nothing_or_tagged() -> None:
    """Members are leaves moving nothing or tagged."""
    rows: list[RankRow] = [
        {"symbol": "W1", "downstream": 0},
        {"symbol": "W2", "downstream": 5},
        {"symbol": "W3", "downstream": 0},
    ]
    f = fruit(Graph(), "a", rows)
    assert f is not None
    assert f["members"] == ["W1", "W3"]
    assert f["class_weight"] == TWO_MEMBERS_WEIGHT


def test_tagged_item_joins_with_its_downstream() -> None:
    """Tagged item joins with its downstream."""
    g = Graph()
    n = waypoint_uri("a", "W2")
    g.add((n, NEMIK.symbol, Literal("W2")))
    g.add((n, NEMIK.workstream, workstream_uri("a")))
    g.add((n, NEMIK.touches, Literal("fruit")))
    f = fruit(g, "a", [{"symbol": "W2", "downstream": 3}])
    assert f is not None
    assert f["members"] == ["W2"]
    assert f["class_weight"] == TAGGED_WEIGHT


def test_no_members_no_row() -> None:
    """No members no row."""
    assert fruit(Graph(), "a", [{"symbol": "W1", "downstream": 2}]) is None


def _graph(spec: dict[str, list[str]]) -> Graph:
    """{symbol: [what it enables]} as ready waypoints in repo a.

    Returns:
        The graph holding those waypoints.

    """
    g = Graph()
    for sym, en in spec.items():
        n = waypoint_uri("a", sym)
        g.add((n, NEMIK.symbol, Literal(sym)))
        g.add((n, NEMIK.workstream, workstream_uri("a")))
        g.add(
            (
                n,
                OSLC_CM.state,
                NEMIK.Ready if not en or en != ["blocked"] else NEMIK.Blocked,
            )
        )
        for t in en:
            if t != "blocked":
                g.add((n, NEMIK.enables, waypoint_uri("b", t)))
                g.add((waypoint_uri("b", t), OSLC_CM.state, NEMIK.Blocked))
    return g


def test_pile_outweighs_a_deep_item_and_leads() -> None:
    """Pile outweighs a deep item and leads."""
    g = _graph(
        {
            "W1": ["W90"],
            "W2": [],
            "W3": [],
            "W4": [],
            "W5": [],
            "W6": [],
            "W7": [],
            "W8": [],
            "W9": [],
            "W10": [],
        }
    )  # W1 moves one stalled peer (8); fruit W2-W10 weigh 9
    rows = rank(g, "a", load_weights())
    assert rows[0]["symbol"] == "W2"
    assert rows[0]["fruit"]["class_weight"] == PILE_WEIGHT


def test_deep_item_outweighing_the_pile_leads() -> None:
    """Deep item outweighing the pile leads."""
    g = _graph({"W1": ["W90"], "W2": [], "W3": []})  # one stalled peer (8) > fruit 2
    assert rank(g, "a", load_weights())[0]["symbol"] == "W1"


def test_a_working_fruit_member_holds_the_class_slot() -> None:
    """Luthen 2026-10-02: with a fruit member working, no other member inherits the class weight."""
    g = _graph(
        {
            "W1": ["W90"],
            "W2": [],
            "W3": [],
            "W4": [],
            "W5": [],
            "W6": [],
            "W7": [],
            "W8": [],
            "W9": [],
            "W10": [],
        }
    )
    g.set((waypoint_uri("a", "W2"), OSLC_CM.state, NEMIK.Working))
    rows = rank(g, "a", load_weights())
    assert rows[0]["symbol"] == "W1"
    assert not any("fruit" in r for r in rows)


def test_a_round_keeps_the_class_whichever_member_is_working() -> None:
    """nemik:W2407: a round keeps the class when a member is working.

    luthen-observability:W2894: W916 stood in for 259 cards and vanished when W941, a member,
    was taken, so the ready cards that filled the round changed with one card's state. The class
    is formed over the ready rows only; the working member is ranked by its own place.
    """
    spec = {"W1": ["W90"], **{f"W{n}": [] for n in range(2, 11)}}
    options = RankOptions(with_working=True)
    ready = rank(_graph(spec), "a", load_weights(), options=options)
    g = _graph(spec)
    g.set((waypoint_uri("a", "W2"), OSLC_CM.state, NEMIK.Working))
    taken = rank(g, "a", load_weights(), options=options)
    assert any("fruit" in r for r in ready)
    assert any("fruit" in r for r in taken)
    assert [r["symbol"] for r in taken if "fruit" in r] != []
    stand_in = next(r for r in taken if "fruit" in r)
    assert stand_in["fruit"]["class_weight"] == READY_PILE_WEIGHT
    assert "W2" not in stand_in["fruit"]["members"]
