from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.rank import frontier


def _wp(g, repo, sym, status="ready", blocked_on=()):
    n = waypoint_uri(repo, sym)
    g.add((n, OSLC_CM.state, STATE[status]))
    for b in blocked_on:
        g.add((n, NEMIK.blockedOn, Literal(b)))
        if b.startswith("W"):
            g.add((n, NEMIK.waitsFor, waypoint_uri(repo, b)))
    return n


def test_goal_frontier_and_its_outside_boundary() -> None:
    # G <- U (umbrella) <- {L1 ready, L2 blocked on b:W9, L3 done}; G <- X foreign open enabler
    g = Graph()
    G = _wp(g, "a", "W1", "blocked", ["W2"])
    U = _wp(g, "a", "W2", "blocked", ["W3", "W4"])
    L1, L2, L3 = _wp(g, "a", "W3"), _wp(g, "a", "W4", "blocked", ["b:W9"]), _wp(g, "a", "W5", "done")
    X = _wp(g, "c", "W7")
    for s, o in ((U, G), (L1, U), (L2, U), (L3, U), (X, G)):
        g.add((s, NEMIK.enables, o))
    leaves, outside = frontier(g, G)
    assert leaves == {L1, L2}
    assert outside == {"b:W9", "c:W7"}


def test_clear_path_has_empty_outside_and_lone_goal_is_its_own_frontier() -> None:
    g = Graph()
    G, L = _wp(g, "a", "W1", "blocked", ["W2"]), _wp(g, "a", "W2")
    g.add((L, NEMIK.enables, G))
    assert frontier(g, G) == ({L}, set())
    solo = _wp(g, "a", "W8")
    assert frontier(g, solo) == ({solo}, set())
