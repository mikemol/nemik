"""nemik:W178: low-hanging fruit as one virtual row."""

from rdflib import Graph, Literal

from nemik.adapter import NEMIK
from nemik.rank import fruit


def test_members_are_leaves_moving_nothing_or_tagged() -> None:
    rows = [{"symbol": "W1", "downstream": 0}, {"symbol": "W2", "downstream": 5}, {"symbol": "W3", "downstream": 0}]
    f = fruit(Graph(), "a", rows)
    assert f["members"] == ["W1", "W3"] and f["class_weight"] == 2


def test_tagged_item_joins_with_its_downstream() -> None:
    from nemik.adapter import waypoint_uri, workstream_uri
    g = Graph()
    n = waypoint_uri("a", "W2")
    g.add((n, NEMIK.symbol, Literal("W2")))
    g.add((n, NEMIK.workstream, workstream_uri("a")))
    g.add((n, NEMIK.touches, Literal("fruit")))
    f = fruit(g, "a", [{"symbol": "W2", "downstream": 3}])
    assert f["members"] == ["W2"] and f["class_weight"] == 4


def test_no_members_no_row() -> None:
    assert fruit(Graph(), "a", [{"symbol": "W1", "downstream": 2}]) is None
