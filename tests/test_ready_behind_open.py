"""nemik:W465: a card stored ready behind one open enabler is flagged; the umbrella rule keeps the rest."""

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri
from nemik.blocks import annotate


def _graph() -> Graph:
    # r:W1 (ready) enables r:W2 (ready) enables r:W3 (ready); r:W4 is done and enables r:W5 (ready)
    g = Graph()
    for sym, state in (("W1", NEMIK.Ready), ("W2", NEMIK.Ready), ("W3", NEMIK.Ready)):
        g.add((waypoint_uri("r", sym), OSLC_CM.state, state))
    g.add((waypoint_uri("r", "W4"), OSLC_CM.state, NEMIK.Done))
    g.add((waypoint_uri("r", "W5"), OSLC_CM.state, NEMIK.Ready))
    g.add((waypoint_uri("r", "W1"), NEMIK.enables, waypoint_uri("r", "W2")))
    g.add((waypoint_uri("r", "W2"), NEMIK.enables, waypoint_uri("r", "W3")))
    g.add((waypoint_uri("r", "W4"), NEMIK.enables, waypoint_uri("r", "W5")))
    return g


def test_a_chain_of_ready_cards_flags_all_but_its_head() -> None:
    g = _graph()
    annotate(g)
    flagged = {s for s, _, _ in g.triples((None, NEMIK.readyBehindOpen, None))}
    assert flagged == {waypoint_uri("r", "W2"), waypoint_uri("r", "W3")}


def test_a_landed_enabler_does_not_count() -> None:
    g = _graph()
    annotate(g)
    assert (waypoint_uri("r", "W5"), NEMIK.readyBehindOpen, None) not in g
