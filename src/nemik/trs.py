# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W448: a repo's queue and ledger as an OSLC Tracked Resource Set (TRS 2.0).

TRS is the incremental feed OSLC tools already consume (IBM's LQE ingests TRS sources; W373's study
of Jazz): a trs:Base listing the tracked resources, and a trs:ChangeLog of numbered Creation,
Modification and Deletion events, so a reader syncs by cursor instead of re-reading everything.

All of it is derived, nothing new is recorded:
- the base is the repo's cards (every waypoint the queue holds);
- each ledger line that names a card is an event on that card, its line number the trs:order;
- a card's first event is its Creation, later ones Modifications;
- a card the ledger names that the queue no longer holds was dropped: a Deletion after its last
event.
"""

from __future__ import annotations

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, XSD
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, workstream_uri

TRS = Namespace("http://open-services.net/ns/core/trs#")
LDP = Namespace("http://www.w3.org/ns/ldp#")


def _line(activity: Node) -> int:
    return int(str(activity).rsplit("/", 1)[-1])


def trs(
    repo: str, queue: Graph, ledger: Graph, withheld: frozenset[str] = frozenset()
) -> Graph:
    """The TRS graph for `repo`: <ws>/trs/base and <ws>/trs/changelog.

    A card whose URI is in `withheld` (nemik:W449: luthen's withheld list) is in neither the base
    nor any change event; its events are skipped whole, so a reader cannot even learn that it
    changed.
    """
    ws = workstream_uri(repo)
    base, log = URIRef(f"{ws}/trs/base"), URIRef(f"{ws}/trs/changelog")
    g = Graph()
    g.bind("trs", TRS)
    g.bind("ldp", LDP)
    cards = {
        c
        for c in queue.subjects(NEMIK.workstream, ws)
        if (c, OSLC_CM.state, None) in queue and str(c) not in withheld
    }
    g.add((base, RDF.type, TRS.Base))
    for card in sorted(cards, key=str):
        g.add((base, LDP.member, card))
    events = sorted(
        (_line(act), card)
        for act, card in ledger.subject_objects(PROV.used)
        if (act, NEMIK.workstream, ws) in ledger and str(card) not in withheld
    )
    g.add((log, RDF.type, TRS.ChangeLog))
    seen: set[Node] = set()
    last: dict[Node, int] = {}
    for order, card in events:
        kind = TRS.Modification if card in seen else TRS.Creation
        seen.add(card)
        last[card] = order
        _event(g, log, kind, card, order)
    tail = max((o for o, _ in events), default=-1)
    for card in sorted(seen - cards, key=str):
        tail += 1
        _event(g, log, TRS.Deletion, card, tail)
    return g


def turtle(
    repo: str, queue: Graph, ledger: Graph, withheld: frozenset[str] = frozenset()
) -> dict[str, str]:
    """{"base": Turtle, "changelog": Turtle} for `repo`: the two resources a TRS reader fetches."""
    g = trs(repo, queue, ledger, withheld)
    ws = workstream_uri(repo)
    log = URIRef(f"{ws}/trs/changelog")
    out: dict[str, str] = {}
    for part, root in (("base", URIRef(f"{ws}/trs/base")), ("changelog", log)):
        sub = Graph()
        sub.bind("trs", TRS)
        sub.bind("ldp", LDP)
        for t in g.triples((root, None, None)):
            sub.add(t)
        if part == "changelog":
            for ev in g.objects(log, TRS.change):
                for t in g.triples((ev, None, None)):
                    sub.add(t)
        out[part] = sub.serialize(format="turtle")
    return out


def _event(g: Graph, log: URIRef, kind: URIRef, card: Node, order: int) -> None:
    ev = URIRef(f"{log}/{order}")
    g.add((log, TRS.change, ev))
    g.add((ev, RDF.type, kind))
    g.add((ev, TRS.changed, card))
    g.add((ev, TRS.order, Literal(order, datatype=XSD.integer)))
