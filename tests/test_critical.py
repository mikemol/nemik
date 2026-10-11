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
