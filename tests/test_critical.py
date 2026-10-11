"""nemik:W313: the critical path and slack of the open dependency graph."""

from __future__ import annotations

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.critical import critical


def _card(g: Graph, sym: str, status: str = "ready"):
    node = waypoint_uri("a", sym)
    g.add((node, OSLC_CM.state, STATE[status]))
    return node


def test_the_longest_chain_has_zero_slack_and_a_side_branch_has_some() -> None:
    g = Graph()
    a, b, c, d = (_card(g, s) for s in ("W1", "W2", "W3", "W4"))
    _card(g, "W5")  # stands alone
    g.add((a, NEMIK.enables, b))  # a -> b -> c is the longest chain
    g.add((b, NEMIK.enables, c))
    g.add((a, NEMIK.enables, d))  # a -> d is a short side branch; e stands alone
    found = critical(g)
    assert found.length == 3
    assert found.chain == ["a:W1", "a:W2", "a:W3"]
    assert found.slack == {
        "a:W1": 0,
        "a:W2": 0,
        "a:W3": 0,
        "a:W4": 1,
        "a:W5": 2,
    }


def test_a_scope_bounds_the_chain_to_a_repo_or_a_cone() -> None:
    # nemik:W333: a:W1 -> b:W1 -> b:W2 crosses repos; a:W9 stands alone in a.
    from nemik.critical import cone, critical, repo_scope

    g = Graph()
    a1 = waypoint_uri("a", "W1")
    b1, b2 = waypoint_uri("b", "W1"), waypoint_uri("b", "W2")
    a9 = waypoint_uri("a", "W9")
    for node in (a1, b1, b2, a9):
        g.add((node, OSLC_CM.state, STATE["ready"]))
    g.add((a1, NEMIK.enables, b1))
    g.add((b1, NEMIK.enables, b2))
    assert critical(g).chain == ["a:W1", "b:W1", "b:W2"]
    assert repo_scope(g, "b") == {"b:W1", "b:W2"}
    assert critical(g, repo_scope(g, "b")).chain == ["b:W1", "b:W2"]
    assert cone(g, "b:W1") == {"a:W1", "b:W1", "b:W2"}
    assert cone(g, "a:W9") == {"a:W9"}
    assert critical(g, cone(g, "a:W9")).chain == ["a:W9"]
    assert cone(g, "x:W0") == set()


def _fan_in(order: list[int]) -> Graph:
    # nemik:W344: W1 waits on ten leaves W2..W11 (ten chains of length 2 tie); W12 stands alone.
    g = Graph()
    nodes = {i: _card(g, f"W{i}") for i in order}
    for i in range(2, 12):
        g.add((nodes[i], NEMIK.enables, nodes[1]))
    return g


def test_tied_longest_chains_are_all_marked_and_graded_not_picked_by_sort_order() -> (
    None
):
    from nemik.critical import critical

    found = critical(_fan_in(list(range(1, 13))))
    leaves = {f"a:W{i}" for i in range(2, 12)}
    assert found.length == 2
    assert set(found.chain) == leaves | {"a:W1"}  # all ten, not one by sort order
    assert found.rank["a:W1"] == 2 and all(found.rank[c] == 1 for c in leaves)
    # W1 ends ten longest chains; each leaf starts one
    assert found.paths["a:W1"] == 10 and all(found.paths[c] == 1 for c in leaves)
    assert "a:W12" not in found.chain
    # the answer does not depend on the order the cards were added in
    assert critical(_fan_in(list(reversed(range(1, 13))))) == found


def test_a_cycle_is_reported_and_a_chain_is_not() -> None:
    # nemik:W324: x -> y -> z -> x never clears; a -> b is a chain; w waits on itself.
    from nemik.critical import cycles

    g = Graph()
    x, y, z, a, b, w = (_card(g, s) for s in ("W1", "W2", "W3", "W4", "W5", "W6"))
    for src, dst in ((x, y), (y, z), (z, x), (a, b), (w, w)):
        g.add((src, NEMIK.enables, dst))
    assert cycles(g) == [(["a:W1", "a:W2", "a:W3"], False), (["a:W6"], False)]
    # the same cycle with one member blocked on the operator is one the operator can break
    from rdflib import Literal

    g.add((y, NEMIK.blockedKind, Literal("human")))
    assert cycles(g)[0] == (["a:W1", "a:W2", "a:W3"], True)


def test_a_done_card_leaves_the_path_and_a_cycle_does_not_hang() -> None:
    g = Graph()
    a, b, c = _card(g, "W1"), _card(g, "W2", "done"), _card(g, "W3")
    g.add((a, NEMIK.enables, b))
    g.add((b, NEMIK.enables, c))
    assert critical(g).length == 1  # a and c no longer chain through the closed b
    x, y = _card(g, "W7"), _card(g, "W8")
    g.add((x, NEMIK.enables, y))
    g.add((y, NEMIK.enables, x))
    assert critical(g).length >= 1  # terminates
