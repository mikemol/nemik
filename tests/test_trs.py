"""nemik:W448: the TRS change log is ordered, creates before it modifies, and deletes what was dropped."""

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import PROV

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri, workstream_uri
from nemik.trs import LDP, TRS, trs


def _graphs() -> tuple[Graph, Graph]:
    ws = workstream_uri("r")
    q, led = Graph(), Graph()
    for sym in ("W1", "W2"):
        card = waypoint_uri("r", sym)
        q.add((card, NEMIK.workstream, ws))
        q.add((card, OSLC_CM.state, NEMIK.Ready))
    # ledger lines 0..3: W1 twice, W2 once, W3 (since dropped) once; line 4 names no card
    lines: list[tuple[int, str | None]] = [
        (0, "W1"),
        (1, "W2"),
        (2, "W1"),
        (3, "W3"),
        (4, None),
    ]
    for n, named in lines:
        act = URIRef(f"{ws}/ledger/{n}")
        led.add((act, RDF.type, PROV.Activity))
        led.add((act, NEMIK.workstream, ws))
        if named:
            led.add((act, PROV.used, waypoint_uri("r", named)))
    return q, led


def _events(g: Graph) -> list[tuple[int, str, str]]:
    out = []
    for ev in g.subjects(TRS.changed, None):
        kind = str(g.value(ev, RDF.type)).rsplit("#", 1)[-1]
        card = str(g.value(ev, TRS.changed)).rsplit("/", 1)[-1]
        out.append((int(str(g.value(ev, TRS.order))), kind, card))
    return sorted(out)


def test_the_change_log_creates_modifies_and_deletes_in_order() -> None:
    g = trs("r", *_graphs())
    assert _events(g) == [
        (0, "Creation", "W1"),
        (1, "Creation", "W2"),
        (2, "Modification", "W1"),
        (3, "Creation", "W3"),
        (4, "Deletion", "W3"),  # the queue no longer holds it
    ]


def test_the_base_is_the_cards_the_queue_holds() -> None:
    g = trs("r", *_graphs())
    base = URIRef(f"{workstream_uri('r')}/trs/base")
    members = {str(m).rsplit("/", 1)[-1] for m in g.objects(base, LDP.member)}
    assert members == {"W1", "W2"}
    assert (base, RDF.type, TRS.Base) in g


def test_orders_are_unique_integers() -> None:
    orders = [o for o, _, _ in _events(trs("r", *_graphs()))]
    assert len(orders) == len(set(orders))
    assert all(isinstance(Literal(o).toPython(), int) for o in orders)
