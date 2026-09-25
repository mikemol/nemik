"""Paths-forward queue -> OSLC CM ChangeRequests, read through mtools' own loader.

The adapter never parses the state file itself: `mikemol.pathsforward.store.load` is the one
reader, so schema drift across repos is mtools' problem to absorb, not a second parser's.
"""

from __future__ import annotations

import re
from pathlib import Path

from mikemol.pathsforward import ledger, model, store
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDFS, XSD

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


OPERATOR = URIRef(f"{BASE}operator")
_SESSION = re.compile(r"^(?P<repo>.+)-[0-9a-f]{2}$")  # a ListAgents session name: <repo>-<2 hex>
_QUALIFIED = re.compile(r"^(?P<repo>[\w.-]+):(?P<sym>W\d+)$")
_OPERATOR_WORDS = ("operator", "user", "mikemol", "human")


def resolve_blocker(repo: str, text: str, known: frozenset[str]) -> URIRef | None:
    """Read a free-text blocked_on value as an edge, when it unambiguously names one.

    blocked_on is free text upstream (see the friction report on summit's floor); these are the
    shapes agents actually write, measured 2026-09-25. Anything else stays a literal only.
      W<n>                 a waypoint in the same workstream
      <repo>:W<n>          a waypoint in another workstream (the form ledgers already use)
      <repo>, <repo>-<hh>  that workstream (a repo name, or a session name for it)
      operator|user|...    the operator
    """
    t = text.strip()
    if model.symbol_number(t) is not None:
        return waypoint_uri(repo, t)
    if (m := _QUALIFIED.match(t)) and m["repo"] in known:
        return waypoint_uri(m["repo"], m["sym"])
    head = t.split()[0] if t.split() else ""
    for cand in (head, (m := _SESSION.match(head)) and m["repo"]):
        if cand and cand in known:
            return workstream_uri(cand)
    if head.lower().split("(")[0] in _OPERATOR_WORDS:
        return OPERATOR
    return None


def queue_graph(repo: str, state_path: Path, known: frozenset[str] = frozenset()) -> Graph:
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
        # strlist reads a bare string as one element, which hid el-openglo's 45 comma-joined
        # fields; record the raw shape so the shapes can see it.
        for field in ("enables", "touches", "blocked_on"):
            if isinstance(w.get(field), str):
                g.add((node, NEMIK.stringNotList, Literal(field)))
        for target in model.strlist(w, "enables"):
            g.add((node, NEMIK.enables, waypoint_uri(repo, target)))
        for who in model.strlist(w, "blocked_on"):
            g.add((node, NEMIK.blockedOn, Literal(who)))
            if target := resolve_blocker(repo, who, known):
                g.add((node, NEMIK.waitsFor, target))
        if kind := model.text(w, "blocked_kind"):
            g.add((node, NEMIK.blockedKind, Literal(kind)))
        for tag in model.strlist(w, "touches"):
            g.add((node, NEMIK.touches, Literal(tag)))
        if issued := model.text(w, "issued_at"):
            g.add((node, DCTERMS.created, Literal(issued)))
        # mtools 2e21902: derived from the tick lock at mint time, never by the agent.
        if during := model.text(w, "minted_during"):
            g.add((node, NEMIK.mintedDuring, Literal(during)))
        if cause := model.text(w, "caused_by"):
            cause_ref = waypoint_uri(repo, cause) if model.symbol_number(cause) is not None else Literal(cause)
            g.add((node, PROV.wasInformedBy, cause_ref))
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


# Ledger kind -> effort class. Only `tick` has a defined meaning upstream (see the friction report
# on summit's floor); the rest is nemik's reading of observed use, kept explicit so it can be argued.
KIND_CLASS = {
    "tick": "forecast",
    "arm": "forecast",
    "manual": "interrupt",
    "msg": "interrupt",
    "peer": "interrupt",
    "op": "interrupt",
    "main": "interrupt",
    "swarm": "interrupt",
}


def ledger_graph(repo: str, ledger_path: Path) -> tuple[Graph, int]:
    """Translate one ledger into PROV activities; return (graph, unparsed line count).

    Read through mtools' `ledger.read`, never re-split here. Each parsed line is a prov:Activity
    that, when it names a symbol, prov:used that waypoint, so interrupt and forecast effort land on
    the same nodes the dependency edges join.
    """
    g = bind(Graph())
    g.bind("prov", PROV)
    unparsed = 0
    ws = workstream_uri(repo)
    for n, rec in enumerate(ledger.read(ledger_path)):
        if isinstance(rec, ledger.Unparsed):
            unparsed += 1
            continue
        e = rec.entry
        node = URIRef(f"{ws}/ledger/{n}")
        g.add((node, RDF.type, PROV.Activity))
        g.add((node, NEMIK.workstream, ws))
        g.add((node, PROV.startedAtTime, Literal(rec.stamp, datatype=XSD.dateTime)))  # is_stamp since 2293751
        g.add((node, NEMIK.kind, Literal(e.kind)))
        g.add((node, NEMIK.effortClass, Literal(KIND_CLASS.get(e.kind, "unclassified"))))
        g.add((node, NEMIK.outcome, Literal(e.outcome)))
        g.add((node, NEMIK.mechanism, Literal(e.mechanism)))
        g.add((node, RDFS.comment, Literal(e.note)))
        if e.symbol != model.NO_SYMBOL:
            g.add((node, PROV.used, waypoint_uri(repo, e.symbol)))
    return g, unparsed
