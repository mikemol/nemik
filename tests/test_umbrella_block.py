from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.blocks import annotate


def _wp(g, repo, sym, status="ready"):
    n = waypoint_uri(repo, sym)
    g.add((n, OSLC_CM.state, STATE[status]))
    return n


def test_peer_block_on_umbrella_is_flagged_and_on_child_is_not() -> None:
    g = Graph()
    umbrella, child = _wp(g, "b", "W43"), _wp(g, "b", "W115")
    g.add((child, NEMIK.enables, umbrella))
    on_umbrella, on_child = _wp(g, "a", "W46", "blocked"), _wp(g, "a", "W47", "blocked")
    g.add((on_umbrella, NEMIK.waitsFor, umbrella))
    g.add((on_child, NEMIK.waitsFor, child))
    annotate(g)
    assert (on_umbrella, NEMIK.umbrellaBlockOn, umbrella) in g
    assert (on_child, NEMIK.umbrellaBlockOn, None) not in g


def test_umbrella_whose_children_are_all_done_is_not_flagged() -> None:
    g = Graph()
    umbrella, child = _wp(g, "b", "W1"), _wp(g, "b", "W2", "done")
    g.add((child, NEMIK.enables, umbrella))
    waiter = _wp(g, "a", "W9", "blocked")
    g.add((waiter, NEMIK.waitsFor, umbrella))
    annotate(g)
    assert (waiter, NEMIK.umbrellaBlockOn, None) not in g
