# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Paths-forward queue -> OSLC CM ChangeRequests, read through mtools' own loader.

The adapter never parses the state file itself: `mikemol.pathsforward.store.load` is the one
reader, so schema drift across repos is mtools' problem to absorb, not a second parser's.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote

from mikemol.pathsforward import ledger, model, store
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDFS, XSD

from nemik import editverbs, warrants

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class _Terms(Namespace):
    """A Namespace that keeps each term once made (nemik:W411).

    rdflib builds a fresh URIRef on every `NEMIK.x`; the hot loops asked 1.48 M times in one rebuild
    (5.2 s of 36). The term lands in the instance dict, so the next lookup never reaches
    __getattr__.
    """

    def __getattr__(self, name: str) -> URIRef:
        term = super().__getattr__(name)
        self.__dict__[name] = term
        return term


OSLC_CM = _Terms("http://open-services.net/ns/cm#")
OSLC = _Terms("http://open-services.net/ns/core#")
NEMIK = _Terms("https://github.com/mikemol/nemik/ns#")
BASE = "urn:nemik:"

STATE = {
    "ready": NEMIK.Ready,
    "working": NEMIK.Working,
    "blocked": NEMIK.Blocked,
    # nemik:W840 (mtools:W1643): committed, deploy not yet witnessed; open, so closed stays false
    "landed": NEMIK.LandedStatus,
    "done": NEMIK.Done,
}


def bind(g: Graph) -> Graph:
    """Give the graph nemik's namespace prefixes.

    Returns:
        The same graph, bound.

    """
    g.bind("oslc_cm", OSLC_CM)
    g.bind("oslc", OSLC)
    g.bind("nemik", NEMIK)
    g.bind("dcterms", DCTERMS)
    return g


def workstream_uri(repo: str) -> URIRef:
    """Name a repo's workstream.

    Returns:
        The workstream's IRI.

    """
    return URIRef(f"{BASE}{repo}")


def waypoint_uri(repo: str, symbol: str) -> URIRef:
    """Name a card.

    Returns:
        The card's IRI under its repo's workstream.

    """
    return URIRef(f"{BASE}{repo}/{symbol}")


def resource_uri(repo: str, address: str) -> URIRef:
    """Name an apply resource (a Terraform address such as module.a.b_c.d["k"][0]) by IRI.

    Every character outside the unreserved set is percent-encoded, so the address is one valid IRI
    path segment whatever it holds (brackets, quotes, spaces, slashes), and resource_address gives
    it back exactly (nemik:W461). A card symbol such as W12 has nothing to encode and is unchanged.

    Args:
        repo: The repo whose host root publishes the resource.
        address: The resource's address, as the publisher writes it.

    Returns:
        The resource's IRI under the repo.

    """
    return URIRef(f"{BASE}{repo}/{quote(address, safe='')}")


def resource_address(uri: str) -> str:
    """Give back the address a resource_uri names.

    Args:
        uri: An IRI resource_uri made.

    Returns:
        The address with its percent-encoding undone.

    """
    return unquote(uri.removeprefix(BASE).partition("/")[2])


def _instant(text: str) -> Literal:
    """Type a queue timestamp as xsd:dateTime when it is one, else keep it as written (nemik:W530).

    Args:
        text: The stamp as the queue stores it, normally 2026-10-16T14:02:11Z.

    Returns:
        A typed literal when the text parses as an ISO 8601 instant with an offset, else plain.

    """
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return Literal(text)
    return Literal(text, datatype=XSD.dateTime) if parsed.tzinfo else Literal(text)


def _extended(text: str) -> str:
    """Rewrite the writer's completed stamp in the extended ISO form (nemik:W530).

    Args:
        text: The stamp as the writer stores it, the iCalendar basic form 20261004T205827Z.

    Returns:
        The same instant as 2026-10-04T20:58:27+00:00, or '' when the text is not an instant.

    """
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return ""
    return parsed.isoformat() if parsed.tzinfo else ""


def reference_uri(repo: str, ref: str) -> URIRef:
    """A local `W<n>` or a foreign `<repo>:W<n>` (mtools 9236d5e) as a waypoint IRI."""
    if foreign := model.foreign_symbol(ref):
        return waypoint_uri(foreign[0], f"W{foreign[1]}")
    return waypoint_uri(repo, ref)


OPERATOR = URIRef(f"{BASE}operator")
_SESSION = re.compile(
    r"^(?P<repo>.+)-[0-9a-f]{2}$"
)  # a ListAgents session name: <repo>-<2 hex>
_OPERATOR_WORDS = ("operator", "user", "mikemol", "mike", "human")
# nemik:W553, W555: words that blur the change-lifecycle steps, in a card's next step and in a run
# row's detail. Not strays, by name: rolled out, activation, promoted, pushed.
_STRAYS = re.compile(
    r"\b(?:armed|shipped|host-shipped|takes effect|rides the next apply|deployed"
    r"|live(?!\s+(?:session|sessions|loop|queue|view|reader|data|graph|fleet)))\b",
    flags=re.IGNORECASE,
)


# nemik:W1011 (retro gate G8): evidence that a command was run and what it answered: the word ran or
# executed, an exit status, or a shell prompt line. A handoff to the operator with none of these has
# not been probed locally, which the skill calls evasion.
_PROBE = re.compile(
    r"\bran\b|\bexecuted\b|\bexit(?:ed)?(?:\s+(?:code|status))?\s*\d+|^\s*\$ ",
    flags=re.IGNORECASE | re.MULTILINE,
)


def has_probe(text: str) -> bool:
    """Say whether evidence records an executed probe.

    Returns:
        True when the text says a command ran, gives an exit status, or shows a shell prompt line.

    """
    return _PROBE.search(text) is not None


def stray_words(text: str) -> list[str]:
    """Find the words in a text that blur the change-lifecycle steps.

    Args:
        text: A card's next step, or a run row's detail.

    Returns:
        The distinct words found, lower-cased and sorted.

    """
    found: list[str] = _STRAYS.findall(text)
    return sorted({word.lower() for word in found})


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
    if (foreign := model.foreign_symbol(t)) and foreign[0] in known:
        return waypoint_uri(foreign[0], f"W{foreign[1]}")
    # the leading token, less a trailing ":" / "," / possessive "'s" ("luthen-observability: ...",
    # "substrate's fixture pair", "substrate-de: settle ...")
    head = re.sub(r"(['’]s|[:,])$", "", t.split()[0]) if t.split() else ""
    for cand in (head, (m := _SESSION.match(head)) and m["repo"]):
        if cand and cand in known:
            return workstream_uri(cand)
    if head.lower().split("(")[0].rstrip(":,") in _OPERATOR_WORDS:
        return OPERATOR
    return None


def load_state(state_path: Path) -> model.State:
    """A queue as mtools' own loader reads it, for the modules that judge a queue unchanged.

    This module stays the one place that calls `store.load` (the single-writer-boundary claim).
    Raises store.UnreadableStateError if mtools refuses it.
    """
    return store.load(state_path)


# nemik:W402: parsed graphs by (what was asked, the file's stamp). A rebuild re-parses only the
# files that moved; a new or vanished repo changes `known` and so every queue's key. One entry per
# (kind, repo): a moved file replaces its stale entry instead of growing the cache.
_PARSED: dict[tuple[str, str], tuple[tuple[object, ...], Graph, int]] = {}
# nemik:W1096: whether the cache above is kept at all. A long-lived reader wants it; a one-shot
# build (nemik-serve --publish) parses each file once and never asks again, so the cache only holds
# a second copy of every queue and ledger graph beside the copy it hands out (measured: the whole
# card-and-edge graph is held several times at the build's peak).
_KEEP = [True]


def forget_parsed() -> None:
    """Stop keeping parsed graphs and drop what is kept; a one-shot build calls this first."""
    _KEEP[0] = False
    _PARSED.clear()


def parsed_count() -> int:
    """Count the parsed graphs kept (nemik:W1096), to see that a one-shot build keeps none.

    Returns:
        How many (kind, repo) entries the parse cache holds.

    """
    return len(_PARSED)


def _stamped(
    kind: str,
    repo: str,
    path: Path,
    extra: object,
    build: Callable[[], tuple[Graph, int]],
) -> tuple[Graph, int]:
    """Answer `build()` from the cache while `path` is unchanged; always a fresh copy to mutate."""
    if not _KEEP[0]:
        return build()
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size, st.st_ino, extra)
    hit = _PARSED.get((kind, repo))
    if hit is None or hit[0] != key:
        g, n = build()
        hit = (key, g, n)
        _PARSED[kind, repo] = hit
    copy = Graph()
    for prefix, ns in hit[1].namespaces():
        copy.bind(prefix, ns, override=True)
    copy += hit[1]
    return copy, hit[2]


def queue_graph(
    repo: str, state_path: Path, known: frozenset[str] = frozenset()
) -> Graph:
    """Translate one repo's queue. Raises store.UnreadableStateError if mtools refuses it."""
    return _stamped(
        "queue",
        repo,
        state_path,
        known,
        lambda: (_queue_graph(repo, state_path, known), 0),
    )[0]


def _queue_graph(repo: str, state_path: Path, known: frozenset[str]) -> Graph:
    state = store.load(state_path)
    g = bind(Graph())
    ws = workstream_uri(repo)
    g.add((ws, RDF.type, NEMIK.Workstream))
    # ⚑ mtools' own order (what the session works next), carried as data so nemik-rank can compare
    # it to cross-repo weight without a second reader of the state file (nemik:W39).
    position = {id(w): i for i, w in enumerate(model.ordered(state.waypoints))}
    for w in state.waypoints:
        symbol = model.text(w, "symbol")
        node = waypoint_uri(repo, symbol)
        g.add((node, NEMIK.queuePosition, Literal(position[id(w)])))
        status = model.text(w, "status")
        g.add((node, RDF.type, OSLC_CM.ChangeRequest))
        g.add((node, NEMIK.workstream, ws))
        # nemik:W530: the workstream is the card's OSLC service provider (OSLC Core 3.0:
        # "a link to the resource's OSLC Service Provider")
        g.add((node, OSLC.serviceProvider, ws))
        g.add((node, NEMIK.symbol, Literal(symbol)))
        # nemik:W530: the standard terms beside the nemik ones, so no reader breaks
        g.add((node, DCTERMS.identifier, Literal(symbol)))
        g.add((node, DCTERMS.title, Literal(model.text(w, "title"))))
        g.add((node, OSLC_CM.state, STATE.get(status, Literal(status))))
        g.add((node, OSLC_CM.closed, Literal(status == "done", datatype=XSD.boolean)))
        # strlist reads a bare string as one element, which hid el-openglo's 45 comma-joined
        # fields; record the raw shape so the shapes can see it.
        for field in ("enables", "touches", "blocked_on"):
            if isinstance(w.get(field), str):
                g.add((node, NEMIK.stringNotList, Literal(field)))
        for target in model.strlist(w, "enables"):
            g.add((node, NEMIK.enables, reference_uri(repo, target)))
        for who in model.strlist(w, "blocked_on"):
            g.add((node, NEMIK.blockedOn, Literal(who)))
            if waited := resolve_blocker(repo, who, known):
                g.add((node, NEMIK.waitsFor, waited))
        if kind := model.text(w, "blocked_kind"):
            g.add((node, NEMIK.blockedKind, Literal(kind)))
        # nemik:W343 (mtools:W1511): any of these may deliver what the card wants; a fallback that
        # never changes the card's state or its blockers.
        for supplier in model.strlist(w, "acceptable_suppliers"):
            g.add((node, NEMIK.acceptableSupplier, reference_uri(repo, supplier)))
        if want := model.text(w, "want").strip():
            g.add((node, NEMIK.wantText, Literal(want)))
        # nemik:W598: the card's warrants (PROV-O JSON-LD, mtools:W1384) join the graph; one
        # that does not parse is marked, not guessed at.
        for bad in warrants.attach(g, w):
            g.add((node, NEMIK.malformedWarrant, Literal(bad)))
        if warrants.claims_ruling(
            w
        ):  # nemik:W597: an operator ruling in prose, no warrant
            g.add((node, NEMIK.claimsRuling, Literal("operator ruling in prose")))
        for tag in model.strlist(w, "touches"):
            g.add((node, NEMIK.touches, Literal(tag)))
            g.add((node, DCTERMS.subject, Literal(tag)))
        # nemik:W544 (mtools:W1276): the repo files the next step names, as written. Paths only; the
        # EditDeclaredShape in shapes.ttl compares them with the file:<path>!w touches.
        named = re.findall(
            r"(?:[\w.-]+/)*[\w-]+\.(?:py|ttl|ya?ml|json|md|html|toml|js)\b",
            model.text(w, "next_bounded_step"),
        )
        for path in sorted(set(named)):
            g.add((node, NEMIK.namesFile, Literal(path)))
        # nemik:W627: and the ones it says it CHANGES, which a drafted manifest may propose
        for path in editverbs.edited_paths(model.text(w, "next_bounded_step")):
            g.add((node, NEMIK.editsFile, Literal(path)))
        # nemik:W488: whether the card still states a next step; an umbrella with none and every
        # child done is realized by construction (UmbrellaCompleteShape).
        if model.text(w, "next_bounded_step").strip():
            g.add((node, NEMIK.hasNextStep, Literal("true", datatype=XSD.boolean)))
        # nemik:W612 (mtools:W1426): the manifest of planned changes (exact repo-relative files)
        # and a size class; ManifestShape and OversizeShape read them, and nemik.stackable too.
        for planned in model.strlist(w, "manifest"):
            g.add((node, NEMIK.plannedPath, Literal(planned)))
        if size := model.text(w, "size_class").strip():
            g.add((node, NEMIK.sizeClass, Literal(size)))
        # nemik:W1011: the evidence holds an executed probe (retro gate G8)
        if has_probe(model.text(w, "evidence")):
            g.add((node, NEMIK.probeRecorded, Literal("true", datatype=XSD.boolean)))
        # nemik:W553 (github-8f 2026-10-15): words that blur the change-lifecycle steps.
        for word in stray_words(model.text(w, "next_bounded_step")):
            g.add((node, NEMIK.strayWord, Literal(word)))
        # nemik:W174: weather. Waypoints whose witnesses are the same query wait on the same outage,
        # so they share one weather id: a hash of the query with its whitespace collapsed. The query
        # text itself stays out of the graph (it may name hosts or endpoints).
        if wq := " ".join(model.text(w, "witness").split()):
            import hashlib

            g.add(
                (
                    node,
                    NEMIK.weather,
                    Literal("wx:" + hashlib.sha256(wq.encode()).hexdigest()[:10]),
                )
            )
        if tb := model.ticks(w):
            g.add((node, NEMIK.ticksBlocked, Literal(tb)))
        if issued := model.text(w, "issued_at"):
            g.add((node, DCTERMS.created, _instant(issued)))
        # nemik:W530: the close time the writer stamps on a completed card, as oslc_cm:closeDate
        # (OSLC CM 3.0: the date no further work is intended), typed as xsd:dateTime
        if closed_at := _extended(model.text(w, "completed")):
            g.add((node, OSLC_CM.closeDate, _instant(closed_at)))
        # nemik:W841 (mtools:W1643): a card whose change is deployed says so (deploys), and the
        # writer stamps the moment it entered landed once (landed_at, RFC 5545 UTC, like completed)
        if model.text(w, "deploys").lower() == "true":
            g.add((node, NEMIK.deploys, Literal("true", datatype=XSD.boolean)))
        if landed_at := _extended(model.text(w, "landed_at")):
            g.add((node, NEMIK.landedAt, _instant(landed_at)))
        # nemik:W616: when the card was last worked, for the stalled and progress-invisible checks
        if worked := model.text(w, "last_worked"):
            g.add((node, NEMIK.lastWorked, _instant(worked)))
        # mtools 2e21902: derived from the tick lock at mint time, never by the agent.
        if during := model.text(w, "minted_during"):
            g.add((node, NEMIK.mintedDuring, Literal(during)))
        # mtools:W248: the WV:1 vector and who wrote it, carried as written; nemik.score reads it
        # through mtools' own parser and owns the band (nemik:W131).
        if vec := model.text(w, "vector"):
            g.add((node, NEMIK.vector, Literal(vec)))
        if src := model.text(w, "vector_source"):
            g.add((node, NEMIK.vectorSource, Literal(src)))
        # nemik:W275 (operator 2026-10-10: a letter is a waypoint's evidence in file form): the
        # letter files a waypoint cites in its evidence or next step, as written. Paths only: the
        # evidence text itself stays out of the graph.
        for text in (model.text(w, "evidence"), model.text(w, "next_bounded_step")):
            for path in re.findall(
                r"(?:[\w.-]+/inbox/[\w./-]+\.md|\.claude/letters/[\w./-]+\.md)", text
            ):
                g.add((node, NEMIK.letter, Literal(path)))
        # nemik:W276: mtools:W930/W931's `attachments` [{path, sha256}] are the stored form of the
        # same citation: a repo-relative file pinned by hash, read through mtools' own parser.
        from mikemol.pathsforward import attach

        for attached, _digest in attach.entries(w):
            g.add((node, NEMIK.letter, Literal(attached)))
        # mtools:W300: RFC 5545 DTSTART/DUE values, kept exactly as written (a DATE, a UTC
        # DATE-TIME, or TZID=Zone:local); nemik.vtodo renders them as properties (nemik:W134).
        # mtools:W1687 adds `location`, where it takes place, free text (nemik:W722).
        for field, pred in (
            ("dtstart", NEMIK.dtstart),
            ("due", NEMIK.due),
            ("location", NEMIK.location),
        ):
            if val := model.text(w, field):
                g.add((node, pred, Literal(val)))
        # mtools:W309: an RFC 5545 RRULE (verbatim) and its EXDATEs; vtodo passes them through, and
        # expanding occurrences for nemik-wake is nemik:W145.
        if rule := model.text(w, "rrule"):
            g.add((node, NEMIK.rrule, Literal(rule)))
        for ex in model.strlist(w, "exdates"):
            g.add((node, NEMIK.exdate, Literal(ex)))
        # mtools:W310: completed occurrences, {RECURRENCE-ID: COMPLETED}; the ids are what skip.
        for rid in sorted(model.strmap(w, "occurrences")):
            g.add((node, NEMIK.occurrenceDone, Literal(rid)))
        # mtools:W279: VALARM triggers, verbatim; nemik.alarm resolves them, nemik-wake fires them.
        for trig in model.strlist(w, "alarms"):
            g.add((node, NEMIK.alarm, Literal(trig)))
        if cause := model.text(w, "caused_by"):
            cause_ref = (
                reference_uri(repo, cause)
                if model.is_reference(cause)
                else Literal(cause)
            )
            g.add((node, PROV.wasInformedBy, cause_ref))
    for r in state.residue:
        symbol = model.text(r, "symbol")
        node = waypoint_uri(repo, symbol)
        g.add((node, RDF.type, NEMIK.Dropped))
        g.add((node, NEMIK.workstream, ws))
        g.add((node, NEMIK.symbol, Literal(symbol)))
        g.add((node, DCTERMS.title, Literal(model.text(r, "title"))))
    return g


# Ledger kind -> effort class. Only `tick` has a defined meaning upstream (see the friction report
# on summit's floor); the rest is nemik's reading of observed use, kept explicit so it can be
# argued.
KIND_CLASS = {
    "tick": "forecast",
    "arm": "forecast",
    "manual": "interrupt",
    "msg": "interrupt",
    "peer": "interrupt",
    "op": "interrupt",
    "main": "interrupt",
    "swarm": "interrupt",
    # nemik:W698: the writer's one line per status transition (mtools:W1372) is bookkeeping, neither
    # planned nor unplanned work, so it stays out of toil_share.
    "status": "bookkeeping",
    # nemik:W701: the writer's edge-pruned line for each blocker a prune removes (mtools:W1599).
    "prune": "bookkeeping",
}


def ledger_graph(repo: str, ledger_path: Path) -> tuple[Graph, int]:
    """Translate one ledger into PROV activities; return (graph, unparsed line count).

    Read through mtools' `ledger.read`, never re-split here. Each parsed line is a prov:Activity
    that, when it names a symbol, prov:used that waypoint, so interrupt and forecast effort land on
    the same nodes the dependency edges join.
    """
    return _stamped(
        "ledger", repo, ledger_path, None, lambda: _ledger_graph(repo, ledger_path)
    )


def _ledger_graph(repo: str, ledger_path: Path) -> tuple[Graph, int]:
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
        g.add(
            (node, PROV.startedAtTime, Literal(rec.stamp, datatype=XSD.dateTime))
        )  # is_stamp since 2293751
        g.add((node, NEMIK.kind, Literal(e.kind)))
        g.add(
            (node, NEMIK.effortClass, Literal(KIND_CLASS.get(e.kind, "unclassified")))
        )
        g.add((node, NEMIK.outcome, Literal(e.outcome)))
        g.add((node, NEMIK.mechanism, Literal(e.mechanism)))
        g.add((node, RDFS.comment, Literal(e.note)))
        if e.symbol != model.NO_SYMBOL:
            g.add((node, PROV.used, reference_uri(repo, e.symbol)))
        if e.session:
            # nemik:W530: the session that wrote the line is a prov:Agent, urn:uuid as its name
            agent = URIRef(f"urn:uuid:{e.session}")
            g.add((agent, RDF.type, PROV.Agent))
            g.add((node, PROV.wasAssociatedWith, agent))
        if e.actor == "operator":
            # nemik:W770: a --lift the writer verified (mtools:W1790) is the operator's own act
            g.add((OPERATOR, RDF.type, PROV.Agent))
            g.add((node, PROV.wasAssociatedWith, OPERATOR))
    return g, unparsed


def ledger_rows(ledger_path: Path) -> list[tuple[str, str, str, str]]:
    """Reduce a ledger to the plain rows ledgersummary sums (nemik:W1097).

    Args:
        ledger_path: The ledger file.

    Returns:
        One (stamp, kind, symbol, effort class) per parsed line in file order; the symbol is empty
        for a line that names no card.

    """
    rows: list[tuple[str, str, str, str]] = []
    for rec in ledger.read(ledger_path):
        if isinstance(rec, ledger.Unparsed):
            continue
        e = rec.entry
        symbol = "" if e.symbol == model.NO_SYMBOL else e.symbol
        # the stamp as the triple holds it (a dateTime literal's lexical form), so a consumer that
        # moves from the triples to the summary publishes the same text
        stamp = str(Literal(rec.stamp, datatype=XSD.dateTime))
        rows.append((stamp, e.kind, symbol, KIND_CLASS.get(e.kind, "unclassified")))
    return rows


def tick_notes(ledger_path: Path) -> list[str]:
    """Give the notes of a ledger's tick lines, oldest first (nemik:W683).

    Args:
        ledger_path: The ledger file.

    Returns:
        The note column of each parsed line whose kind is tick.

    """
    return [
        rec.entry.note
        for rec in ledger.read(ledger_path)
        if not isinstance(rec, ledger.Unparsed) and rec.entry.kind == "tick"
    ]
