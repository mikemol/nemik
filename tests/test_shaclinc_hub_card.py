# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2225: a card with many children is a hub, and its own edges are still judged whole.

3caa25a let a hub's neighbours into the validated subgraph with only the predicates the Workstream
shapes read and no type. That is right for a workstream and wrong for a card that happens to have
more than HUB neighbours (an umbrella with a hundred children): its own `enables` targets lost
their type, and el-openglo:W762 was reported as naming 'a symbol that is neither a waypoint nor
residue' while both its targets existed. The fixture fleet has no such card, so no equivalence
test saw it.
"""

from importlib.resources import files
from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDFS

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.queuefiles import QUEUE, workstream_files
from nemik.shaclinc import HUB, findings, shacl_results

FLEET = Path(__file__).parent / "fixtures" / "fleet"
KIDS = HUB + 5


def _fleet() -> Graph:
    """Read the fixture fleet into one graph.

    Returns:
        The merged, annotated graph.

    """
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def _kid(hub: URIRef, at: int) -> URIRef:
    """Name the `at`-th child of the hub card.

    Returns:
        The child's node.

    """
    return URIRef(f"{hub}-kid{at}")


def _umbrella(g: Graph) -> URIRef:
    """Give one card more children than a hub has, and two enables edges of its own.

    Returns:
        The card.

    """
    cards = sorted(set(g.subjects(OSLC_CM.state, None)), key=str)
    hub = URIRef(str(cards[0]))
    ws = g.value(hub, NEMIK.workstream)
    assert ws is not None
    g.add((hub, NEMIK.enables, cards[1]))
    g.add((hub, NEMIK.enables, cards[2]))
    for at in range(KIDS):
        kid = _kid(hub, at)
        g.add((kid, RDF.type, OSLC_CM.ChangeRequest))
        g.add((kid, NEMIK.symbol, Literal(f"W{9000 + at}")))
        g.add((kid, DCTERMS.title, Literal(f"kid {at}")))
        g.add((kid, OSLC_CM.state, NEMIK.Ready))
        g.add((kid, NEMIK.workstream, ws))
        g.add((kid, PROV.wasInformedBy, hub))
    return hub


def test_a_card_hub_keeps_the_types_of_the_cards_it_enables() -> None:
    """After a child changes, the hub's enables edges still resolve, as in a full run."""
    g, sh = _fleet(), shapes()
    hub = _umbrella(g)
    findings("test-hub-card", g, sh)
    kid = _kid(hub, 0)
    g.remove((kid, OSLC_CM.state, None))
    g.add((kid, OSLC_CM.state, NEMIK.Done))
    inc = sorted(findings("test-hub-card", g, sh))
    full = sorted(
        (f, s, m) for f, rows in shacl_results(g, sh).items() for s, m in rows
    )
    assert inc == full
    assert not any(m.startswith("enables names") for _, _, m in inc)


FOREIGN = URIRef("http://example.org/other#Workstream")


def test_a_foreign_type_named_workstream_does_not_restrict_a_card_hub() -> None:
    """Only the nemik Workstream type restricts a hub; the same name from another vocabulary no."""
    g, sh = _fleet(), shapes()
    hub = _umbrella(g)
    g.add((hub, RDF.type, FOREIGN))
    findings("test-hub-foreign", g, sh)
    kid = _kid(hub, 0)
    g.remove((kid, OSLC_CM.state, None))
    g.add((kid, OSLC_CM.state, NEMIK.Done))
    inc = sorted(findings("test-hub-foreign", g, sh))
    full = sorted(
        (f, s, m) for f, rows in shacl_results(g, sh).items() for s, m in rows
    )
    assert inc == full
    assert not any(m.startswith("enables names") for _, _, m in inc)


def test_no_class_the_enables_shape_accepts_has_a_subclass() -> None:
    """The enables shape asks for the class itself: it equals sh:class while no subclass exists."""
    onto = Graph()
    onto.parse(
        data=files("nemik.data").joinpath("nemik.ttl").read_text(), format="turtle"
    )
    accepted = {OSLC_CM.ChangeRequest, NEMIK.Dropped}
    assert not [
        s for s, _, o in onto.triples((None, RDFS.subClassOf, None)) if o in accepted
    ]
