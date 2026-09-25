"""Paths-forward queue -> OSLC CM ChangeRequests, read through mtools' own loader.

The adapter never parses the state file itself: `mikemol.pathsforward.store.load` is the one
reader, so schema drift across repos is mtools' problem to absorb, not a second parser's.
"""

from __future__ import annotations

from pathlib import Path

from mikemol.pathsforward import model, store
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, XSD

OSLC_CM = Namespace("http://open-services.net/ns/cm#")
NEMIK = Namespace("https://github.com/mikemol/nemik/ns#")
BASE = "urn:nemik:"

STATE = {
    "ready": NEMIK.Ready,
    "working": NEMIK.Working,
    "blocked": NEMIK.Blocked,
    "done": NEMIK.Done,
}


def bind(g: Graph) -> Graph:
    g.bind("oslc_cm", OSLC_CM)
    g.bind("nemik", NEMIK)
    g.bind("dcterms", DCTERMS)
    return g


def workstream_uri(repo: str) -> URIRef:
    return URIRef(f"{BASE}{repo}")


def waypoint_uri(repo: str, symbol: str) -> URIRef:
    return URIRef(f"{BASE}{repo}/{symbol}")


def queue_graph(repo: str, state_path: Path) -> Graph:
    """Translate one repo's queue. Raises store.UnreadableStateError if mtools refuses it."""
    state = store.load(state_path)
    g = bind(Graph())
    ws = workstream_uri(repo)
    g.add((ws, RDF.type, NEMIK.Workstream))
    for w in state.waypoints:
        symbol = model.text(w, "symbol")
        node = waypoint_uri(repo, symbol)
        status = model.text(w, "status")
        g.add((node, RDF.type, OSLC_CM.ChangeRequest))
        g.add((node, NEMIK.workstream, ws))
        g.add((node, NEMIK.symbol, Literal(symbol)))
        g.add((node, DCTERMS.title, Literal(model.text(w, "title"))))
        g.add((node, OSLC_CM.state, STATE.get(status, Literal(status))))
        g.add((node, OSLC_CM.closed, Literal(status == "done", datatype=XSD.boolean)))
        for target in model.strlist(w, "enables"):
            g.add((node, NEMIK.enables, waypoint_uri(repo, target)))
        for who in model.strlist(w, "blocked_on"):
            g.add((node, NEMIK.blockedOn, Literal(who)))
        if kind := model.text(w, "blocked_kind"):
            g.add((node, NEMIK.blockedKind, Literal(kind)))
        for tag in model.strlist(w, "touches"):
            g.add((node, NEMIK.touches, Literal(tag)))
    for r in state.residue:
        symbol = model.text(r, "symbol")
        node = waypoint_uri(repo, symbol)
        g.add((node, RDF.type, NEMIK.Dropped))
        g.add((node, NEMIK.workstream, ws))
        g.add((node, NEMIK.symbol, Literal(symbol)))
        g.add((node, DCTERMS.title, Literal(model.text(r, "title"))))
    for r in state.residue:
        symbol = model.text(r, "symbol")
        node = waypoint_uri(repo, symbol)
        g.add((node, RDF.type, NEMIK.Dropped))
        g.add((node, NEMIK.workstream, ws))
        g.add((node, NEMIK.symbol, Literal(symbol)))
        g.add((node, DCTERMS.title, Literal(model.text(r, "title"))))
    return g
