# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""rank.frontier: a goal's frontier leaves and the boundary outside them."""

from rdflib import Graph, Literal, URIRef

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.rank import frontier


def _wp(
    g: Graph,
    repo: str,
    sym: str,
    status: str = "ready",
    blocked_on: list[str] | tuple[str, ...] = (),
) -> URIRef:
    n = waypoint_uri(repo, sym)
    g.add((n, OSLC_CM.state, STATE[status]))
    for b in blocked_on:
        g.add((n, NEMIK.blockedOn, Literal(b)))
        if b.startswith("W"):
            g.add((n, NEMIK.waitsFor, waypoint_uri(repo, b)))
    return n


def test_goal_frontier_and_its_outside_boundary() -> None:
    """Goal frontier and its outside boundary."""
    # G <- U (umbrella) <- {L1 ready, L2 blocked on b:W9, L3 done}; G <- X foreign open enabler
    g = Graph()
    goal = _wp(g, "a", "W1", "blocked", ["W2"])
    umbrella = _wp(g, "a", "W2", "blocked", ["W3", "W4"])
    leaf1, leaf2, leaf3 = (
        _wp(g, "a", "W3"),
        _wp(g, "a", "W4", "blocked", ["b:W9"]),
        _wp(g, "a", "W5", "done"),
    )
    foreign = _wp(g, "c", "W7")
    for s, o in (
        (umbrella, goal),
        (leaf1, umbrella),
        (leaf2, umbrella),
        (leaf3, umbrella),
        (foreign, goal),
    ):
        g.add((s, NEMIK.enables, o))
    leaves, outside = frontier(g, goal)
    assert leaves == {leaf1, leaf2}
    assert outside == {"b:W9", "c:W7"}


def test_clear_path_has_empty_outside_and_lone_goal_is_its_own_frontier() -> None:
    """Clear path has empty outside and lone goal is its own frontier."""
    g = Graph()
    goal, leaf = _wp(g, "a", "W1", "blocked", ["W2"]), _wp(g, "a", "W2")
    g.add((leaf, NEMIK.enables, goal))
    assert frontier(g, goal) == ({leaf}, set())
    solo = _wp(g, "a", "W8")
    assert frontier(g, solo) == ({solo}, set())


def test_ready_item_with_open_feeder_is_an_umbrella() -> None:
    """Ready item with open feeder is an umbrella."""
    from nemik.rank import is_umbrella

    g = Graph()
    umbrella, leaf = _wp(g, "a", "W1"), _wp(g, "a", "W2")
    g.add((leaf, NEMIK.enables, umbrella))
    assert is_umbrella(g, umbrella) and not is_umbrella(g, leaf)
    g.set((leaf, OSLC_CM.state, STATE["done"]))
    assert not is_umbrella(g, umbrella)


def test_goals_pick_terminal_items_with_on_deck_leaf_and_outside_waits() -> None:
    """Goals pick terminal items with on deck leaf and outside waits."""
    from nemik.adapter import workstream_uri
    from nemik.rank import goals, load_weights

    g = Graph()
    goal, leaf1, leaf2 = (
        _wp(g, "a", "W1", "blocked", ["W2", "W3"]),
        _wp(g, "a", "W2"),
        _wp(g, "a", "W3", "blocked", ["b:W9"]),
    )
    other = _wp(g, "a", "W4")
    for n, s in ((goal, "W1"), (leaf1, "W2"), (leaf2, "W3"), (other, "W4")):
        g.add((n, NEMIK.workstream, workstream_uri("a")))
        g.add((n, NEMIK.symbol, Literal(s)))
    rows = {r["goal"]: r for r in goals(g, "a", load_weights())}
    assert set(rows) == {"W1", "W4"}
    assert (
        rows["W1"]["on_deck"] == "a:W2"
        and rows["W1"]["outside"] == ["b:W9"]
        and not rows["W1"]["clear"]
    )
    assert rows["W4"]["frontier"] == ["a:W4"] and rows["W4"]["clear"]
