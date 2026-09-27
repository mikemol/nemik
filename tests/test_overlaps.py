from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.overlaps import overlaps


def _wp(g: Graph, repo: str, sym: str, status: str, *tags: str) -> None:
    n = waypoint_uri(repo, sym)
    g.add((n, OSLC_CM.state, STATE[status]))
    for t in tags:
        g.add((n, NEMIK.touches, Literal(t)))


def test_live_shared_tags_grouped_and_cross_filters_local() -> None:
    g = Graph()
    _wp(g, "a", "W1", "ready", "docs", "cli")
    _wp(g, "a", "W2", "working", "cli")
    _wp(g, "b", "W7", "ready", "docs")
    _wp(g, "b", "W8", "done", "docs", "cli")  # not live
    _wp(g, "b", "W9", "blocked", "cli")  # not live
    assert overlaps(g) == {"cli": ["a:W1", "a:W2"], "docs": ["a:W1", "b:W7"]}
    assert overlaps(g, cross=True) == {"docs": ["a:W1", "b:W7"]}
