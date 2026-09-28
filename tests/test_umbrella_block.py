from rdflib import Graph, Literal

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


def test_block_on_a_landed_waypoint_is_flagged_and_all_landed_means_ready() -> None:
    g = Graph()
    done, live = _wp(g, "p", "W111", "done"), _wp(g, "p", "W120")
    all_landed, mixed = _wp(g, "p", "W117", "blocked"), _wp(g, "p", "W119", "blocked")
    g.add((all_landed, NEMIK.blockedOn, Literal("W111")))
    g.add((all_landed, NEMIK.waitsFor, done))
    for t in (done, live):
        g.add((mixed, NEMIK.blockedOn, Literal(t.split("/")[-1])))
        g.add((mixed, NEMIK.waitsFor, t))
    annotate(g)
    assert (all_landed, NEMIK.landedBlocker, done) in g
    assert (all_landed, NEMIK.allBlockersLanded, None) in g
    assert (mixed, NEMIK.landedBlocker, done) in g
    assert (mixed, NEMIK.landedBlocker, live) not in g
    assert (mixed, NEMIK.allBlockersLanded, None) not in g


def test_symbol_with_prose_attached_is_malformed_and_clean_forms_are_not() -> None:
    g = Graph()
    w = _wp(g, "p", "W19", "blocked")
    for text in ("W8 (both rewrite the lock)", "W8", "luthen-observability:W185", "operator: decide x"):
        g.add((w, NEMIK.blockedOn, Literal(text)))
    annotate(g)
    assert set(g.objects(w, NEMIK.malformedBlocker)) == {Literal("W8 (both rewrite the lock)")}
