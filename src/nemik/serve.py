# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-serve: a read-only web view of the merged workstream graph.

    /             the dependency view (static page; draws /graph.json)
    /graph.json   waypoints, enables edges, and per-waypoint effort by class, for the page
    /graph.ttl    the merged RDF graph (OSLC CM ChangeRequests + PROV ledger activities)
    /vendor/*     cytoscape, dagre, cytoscape-dagre, vendored so the page never leaves the host
    /metrics      Prometheus text: graph size, last rebuild cost, build info
    /operator     open waypoints blocked on the operator: needs-you / answered / condition / unstated
    /wake         blocked-on workstreams with their liveness: which must be woken, and for what
    /inbound[/<repo>]  open waypoints waiting on <repo> (or anyone), each with the blocker's
                  claiming waypoints: what an agent reads to learn "I am the block, and on what"

The graph is rebuilt only when a queue or ledger file changes (mtime key), so a page poll costs
a stat walk, not a SHACL pass.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path
from typing import Any

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import BASE, NEMIK, OPERATOR, OSLC_CM, bind, ledger_graph
from nemik.blocks import inbound, operator_asks, ref
from nemik.check import LEDGER, QUEUE, default_root, survey, workstream_files
from nemik.exportwire import exports_key, withheld_by_exports
from nemik.luthenseries import board, load
from nemik.outbox import outbox
from nemik.runlogs import runs_graph
from nemik.wake import operator_row, read_liveness, roster
from nemik.withheldage import require_fresh

VENDOR = {"cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.js"}
# nemik:W671: luthen's loop snapshot sits beside the queues in the export (as withheld.json and
# liveness.json do); a published view reads it, refusing one older than SERIES_MAX_AGE, and is
# rebuilt every SERIES_REBUILD_S although no queue changed, since the board is baked in.
SERIES_FILE = "luthen-series.json"
SERIES_MAX_AGE = 900
SERIES_REBUILD_S = 600


class Model:
    def __init__(
        self,
        root: Path,
        withheld: frozenset[str] = frozenset(),
        runs: Path | None = None,
        series: Path | None = None,
        series_max_age: int = 900,
    ) -> None:
        self.root = root
        # nemik:W670: luthen's loop and token snapshot (luthen-series.json), read per request so its
        # age is judged against the clock, never against the last rebuild.
        self.series = series
        self.series_max_age = series_max_age
        # nemik:W565: luthen's published run logs (runs/<stream>.jsonl), read as prov:Activity rows
        # into the graph when a directory is given.
        self.runs = runs
        # nemik:W309: refs luthen withholds from the public view. They are kept out of every NUMBER
        # the view publishes (salience, edge current, history counts), not only out of the node list.
        self.withheld = withheld
        self.key: tuple = ()
        self.graph = bind(Graph())
        self.payload = b"{}"
        self.doc: dict = {
            "operator": [],
            "inbound": [],
        }  # parsed once per rebuild, shared by requests
        self.rebuilds = 0
        self.rebuild_cpu = 0.0
        # nemik:W399: the last rebuild's CPU seconds per phase (parse, annotate, shacl, fleet_checks,
        # ledger, document), so the phase that dominates is measured, not guessed.
        self.phases: dict[str, float] = {}
        self.nodes = self.edges = self.workstreams = 0
        # ThreadingHTTPServer: refresh() runs on every request (nemik:W19). Without this lock,
        # several requests arriving as a queue file changes (e.g. luthen's once-a-minute export)
        # each redo the full survey()+SHACL rebuild concurrently -- wasted CPU under the GIL that
        # can starve the accept loop, not just a duplicated cache miss.
        self._lock = threading.Lock()

    def sources(self) -> list[Path]:
        found = [
            p for name in (QUEUE, LEDGER) for _, p in workstream_files(self.root, name)
        ]
        if self.runs is not None:  # nemik:W565: a changed run log rebuilds the view too
            found += sorted(self.runs.glob("*.jsonl"))
        return found

    def refresh(self) -> None:
        key = tuple((str(p), p.stat().st_mtime_ns) for p in self.sources())
        if key == self.key:
            return
        with self._lock:
            if key == self.key:  # someone else rebuilt while we waited for the lock
                return
            cpu0 = time.process_time()
            phases: dict[str, float] = {}
            g, findings = bind(Graph()), {}
            for repo, qg, fs in survey(self.root, phases):
                findings[repo] = fs
                if qg is not None:
                    g += qg
            t = time.process_time()
            for repo, path in workstream_files(self.root, LEDGER):
                lg, _ = ledger_graph(repo, path)
                g += lg
            if self.runs is not None:
                g += runs_graph(self.runs)[0]
            phases["ledger"] = time.process_time() - t
            self.graph, self.key = g, key
            self.rebuilds += 1
            t = time.process_time()
            numbers = without(g, self.withheld) if self.withheld else None
            doc = to_json(g, findings, numbers)
            phases["document"] = time.process_time() - t
            self.rebuild_cpu = time.process_time() - cpu0
            self.phases = phases
            self.nodes, self.edges, self.workstreams = (
                len(doc["nodes"]),
                len(doc["edges"]),
                len(findings),
            )
            self.doc, self.payload = doc, json.dumps(doc).encode()

    def series_doc(self) -> dict[str, object]:
        """Build the series board from luthen's snapshot (nemik:W670).

        Returns:
            {"board": True, ...} with each repo's state, history and the stranded list, or
            {"board": False, "why": ...} when there is no snapshot or it cannot be trusted
            (missing, unreadable, unversioned, stale, from the future): no board, never a
            guessed one.

        """
        if self.series is None:
            return {"board": False, "why": "no --series file"}
        try:
            snap = load(self.series, int(time.time()), self.series_max_age)
        except OSError:
            return {"board": False, "why": "no snapshot"}  # never a host path
        except (ValueError, TypeError) as e:
            return {"board": False, "why": str(e)}
        ready: dict[str, int] = {}
        for node in self.doc.get("nodes", []):
            cite = f"{node['repo']}:{node.get('symbol', '')}"
            if node["state"] in {"ready", "working"} and cite not in self.withheld:
                ready[node["repo"]] = ready.get(node["repo"], 0) + 1
        return {"board": True, **board(snap, ready)}

    def poke(self) -> None:
        """Keep requests off the rebuild path (nemik:W69, luthen-observability:W146).

        Only the very first request builds synchronously, because there is nothing to serve yet.
        After that, a changed export starts one background rebuild and the request is served the
        last good payload at once, so probes and /metrics never wait on a multi-second survey.
        """
        if self.rebuilds == 0:
            self.refresh()
            return
        key = tuple((str(p), p.stat().st_mtime_ns) for p in self.sources())
        if key != self.key and not self._lock.locked():
            threading.Thread(target=self.refresh, daemon=True).start()

    def metrics(self) -> bytes:
        try:
            ver = version("nemik")
        except PackageNotFoundError:
            ver = "unknown"
        return "\n".join(
            [
                "# TYPE nemik_build_info gauge",
                f'nemik_build_info{{version="{ver}"}} 1',
                "# TYPE nemik_graph_nodes gauge",
                f"nemik_graph_nodes {self.nodes}",
                "# TYPE nemik_graph_edges gauge",
                f"nemik_graph_edges {self.edges}",
                "# TYPE nemik_graph_workstreams gauge",
                f"nemik_graph_workstreams {self.workstreams}",
                "# TYPE nemik_graph_rebuilds_total counter",
                f"nemik_graph_rebuilds_total {self.rebuilds}",
                "# TYPE nemik_graph_rebuild_cpu_seconds gauge",
                f"nemik_graph_rebuild_cpu_seconds {self.rebuild_cpu:.3f}",
                "# TYPE nemik_graph_rebuild_phase_cpu_seconds gauge",
                *(
                    f'nemik_graph_rebuild_phase_cpu_seconds{{phase="{p}"}} {s:.3f}'
                    for p, s in sorted(self.phases.items())
                ),
                "",
            ]
        ).encode()


def local(term) -> str:
    """The last segment of a nemik:/oslc IRI: after '#', '/', or the urn:nemik: prefix."""
    return str(term).removeprefix("urn:nemik:").rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def suppliers_of(g: Graph, card: URIRef) -> list[str]:
    """List the cards that may deliver what a card wants (nemik:W343, mtools:W1511).

    Args:
        g: The merged queue graph.
        card: The waiting card.

    Returns:
        Their citations as repo:W<n>, sorted; empty when the card names none.

    """
    return sorted(ref(o) for o in g.objects(card, NEMIK.acceptableSupplier))


def without(g: Graph, refs: frozenset[str]) -> Graph:
    """nemik:W309: a copy of `g` with every withheld waypoint (and every edge to or from it) removed,
    the graph the public numbers are computed over."""
    from nemik.withheld import _id

    out = Graph()
    gone = {URIRef(_id(r)) for r in refs}
    for s, p, o in g:
        if s not in gone and o not in gone:
            out.add((s, p, o))
    return out


def to_json(g: Graph, findings: dict, numbers: Graph | None = None) -> dict:
    """The view's document. nemik:W403: built with identical flow solves answered once (the ranking,
    edge widths and operator-ask weights each asked for the same repo's solve). nemik:W412: and with
    each graph's per-card facts indexed once."""
    from nemik.index import indexed
    from nemik.salience import memo_audits

    with memo_audits(), indexed():
        return _to_json(g, findings, numbers)


def _to_json(g: Graph, findings: dict, numbers: Graph | None = None) -> dict:
    # nemik:W309: every published number (salience, edge current, ask weight) comes from `gn`, the
    # graph without the withheld waypoints, when there are any; structure still comes from `g`.
    gn = numbers if numbers is not None else g
    effort: dict[str, Counter] = defaultdict(Counter)
    last: dict[str, str] = {}
    for act in g.subjects(RDF.type, PROV.Activity):
        cls = str(g.value(act, NEMIK.effortClass))
        stamp = str(g.value(act, PROV.startedAtTime) or "")
        for wp in g.objects(act, PROV.used):
            effort[str(wp)][cls] += 1
            last[str(wp)] = max(last.get(str(wp), ""), stamp)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for kind, cls in (("waypoint", OSLC_CM.ChangeRequest), ("dropped", NEMIK.Dropped)):
        for n in g.subjects(RDF.type, cls):
            state = (
                local(g.value(n, OSLC_CM.state)).lower()
                if kind == "waypoint"
                else "dropped"
            )
            nodes.append(
                {
                    "id": str(n),
                    "repo": local(g.value(n, NEMIK.workstream)),
                    "symbol": str(g.value(n, NEMIK.symbol)),
                    "title": str(g.value(n, DCTERMS.title) or ""),
                    "state": state,
                    "blocked_on": [str(o) for o in g.objects(n, NEMIK.blockedOn)],
                    "blocked_kind": str(g.value(n, NEMIK.blockedKind) or ""),
                    # nemik:W343: who else may deliver what this card wants, beside its blockers
                    "suppliers": suppliers_of(g, URIRef(str(n))),
                    "want": str(g.value(n, NEMIK.wantText) or ""),
                    "effort": dict(sorted(effort.get(str(n), {}).items())),
                    "last_activity": last.get(str(n), ""),
                    "minted_during": str(g.value(n, NEMIK.mintedDuring) or ""),
                    "caused_by": str(g.value(n, PROV.wasInformedBy) or ""),
                    "weather": str(g.value(n, NEMIK.weather) or ""),
                }
            )
    for s, _, o in g.triples((None, NEMIK.enables, None)):
        edges.append({"source": str(s), "target": str(o), "kind": "enables"})
    # A block on another workstream ends at the blocker's waypoint that claims it, or at an
    # "unclaimed" placeholder inside the blocker's box, never at a bare repo label.
    blocks = inbound(g)
    # One (blocked, blocker) pair can have several inbound rows (linux-sources:W40 waits on the mtools
    # session AND mtools:W24 AND mtools:W46). Keeping only the last row made which claims got drawn
    # depend on hash order (nemik:W119), so the claims are merged.
    by_blocked: dict[tuple[str, str], dict] = {}
    for blk in blocks:
        m = by_blocked.setdefault(
            (blk["blocked"], blk["blocker"]), {**blk, "claimed_by": []}
        )
        m["claimed_by"] = sorted(set(m["claimed_by"]) | set(blk["claimed_by"]))
    for s, _, o in g.triples((None, NEMIK.waitsFor, None)):
        if o == OPERATOR:
            continue  # drawn from operator_asks below, one lane per category
        if (o, RDF.type, NEMIK.Workstream) not in g:
            edges.append({"source": str(s), "target": str(o), "kind": "waits"})
            continue
        b = by_blocked.get((ref(s), local(o)))
        if b is None:  # done, or a block on its own workstream
            continue
        if b["claimed_by"]:
            for c in b["claimed_by"]:
                repo, _, sym = c.partition(":")
                edges.append(
                    {"source": str(s), "target": f"{BASE}{repo}/{sym}", "kind": "waits"}
                )
        else:
            ask = f"ask:{b['blocked']}@{b['blocker']}"
            nodes.append(
                {
                    "id": ask,
                    "repo": b["blocker"],
                    "symbol": "?",
                    "state": "unclaimed",
                    "title": f"nothing in {b['blocker']} claims {b['blocked']} yet",
                    "blocked_on": b["blocked_on"],
                    "blocked_kind": "",
                    "effort": {},
                    "last_activity": "",
                    "minted_during": "",
                    "caused_by": "",
                    "cite": "",
                    "for": b["blocked"],
                }
            )
            edges.append({"source": str(s), "target": ask, "kind": "waits"})
    from nemik.blocks import with_salience

    # nemik:W460: an errand is the operator's own business: nemik-operator lists it, the view does not.
    asks = [a for a in with_salience(gn, operator_asks(g)) if a["category"] != "errand"]
    for a in asks:
        lane_edge: dict[str, Any] = {
            "source": f"{BASE}{a['ref'].replace(':', '/', 1)}",
            "target": f"operator:{a['category']}",
            "kind": "waits",
        }
        # nemik:W298: the demand an ask holds back is its edge's weight.
        if a["salience"]:
            lane_edge["current"] = a["salience"]
        edges.append(lane_edge)
    # nemik:W56: an edge whose upstream end is done no longer holds anything back. For `enables`
    # that end is the source; for `waits` it is the target. open_blockers counts what still does.
    done = {n["id"] for n in nodes if n["state"] == "done"}
    # Distinct upstream items, since W3 enables W1 and W1 waits on W3 name one blocker.
    open_blockers: dict[str, set] = defaultdict(set)
    for e in edges:
        up, down = (
            (e["source"], e["target"])
            if e["kind"] == "enables"
            else (e["target"], e["source"])
        )
        e["satisfied"] = up in done
        if not e["satisfied"]:
            open_blockers[down].add(up)
    for item in nodes:
        item["open_blockers"] = len(open_blockers.get(item["id"], ()))
        if item["id"].startswith(BASE):
            item["cite"] = ref(URIRef(item["id"]))
    # nemik:W135: each ready waypoint's place in its repo's composed nemik-rank order (0 = work it
    # first), so the page can lay out a rank-ordered forest without re-deriving the ranking.
    from nemik.rank import load_composition, load_weights, rank

    weights, comp = load_weights(), load_composition()
    by_id = {n["id"]: n for n in nodes}
    for repo in sorted({n["repo"] for n in nodes if n["state"] == "ready"}):
        for i, r in enumerate(rank(gn, repo, weights, comp)):
            if found := by_id.get(f"{BASE}{repo}/{r['symbol']}"):
                found["rank_pos"], found["band"] = i, r["band_name"]
                if r.get("salience") is not None:
                    found["salience"] = round(r["salience"], 4)
    # nemik:W322: slack (nemik.critical) per open card, and which cards lie on the longest chain, so
    # the page can mark the path that bounds the fleet. Computed over `gn` like every published number.
    from nemik.critical import critical, repo_scope

    crit = critical(gn)
    on_path = set(crit.chain)
    # nemik:W334: each repo's own longest chain, beside the fleet's, for the page's per-repo halo.
    repo_chain = {
        repo: set(critical(gn, repo_scope(gn, repo)).chain)
        for repo in sorted({n["repo"] for n in nodes})
    }
    for item in nodes:
        if item.get("cite") in crit.slack:
            item["slack"] = crit.slack[item["cite"]]
            item["on_path"] = item["cite"] in on_path
            # nemik:W344: the longest chains through this card (ways in x ways out); 1 = no ties
            item["path_count"] = crit.paths.get(item["cite"], 0)
            item["on_path_repo"] = item["cite"] in repo_chain[item["repo"]]
    # nemik:W477: a card stored ready while an open card enables it (nemik:W465's finding) is drawn
    # as waiting: its fill says ready, but the flow model counts it as waiting and gives it no salience.
    from nemik.blocks import ready_behind_open

    behind = {str(s) for s in ready_behind_open(g)}
    for item in nodes:
        if item["id"] in behind:
            item["behind_open"] = True
    # nemik:W264: the demand that crossed each dependency, summed over the ready repos' solves, as
    # the width the page draws the edge with. A `waits` edge runs waiter -> blocker, an `enables`
    # edge prerequisite -> dependent; the flow names a dependency (needing card, prerequisite).
    from nemik.salience import edge_currents

    crossed: dict[tuple[str, str], float] = defaultdict(float)
    for repo in sorted({n["repo"] for n in nodes if n["state"] == "ready"}):
        for pair, amount in edge_currents(
            gn,
            repo,
            weights.local,
            weights.peer,
            weights.peer_blocked,
            weights.operator,
        ).items():
            crossed[pair] += amount
    # nemik:W298: an operator ask is not workable, so the solve above never ends a path at it; the
    # open-ground solve does, and the edges INTO an ask take their current from it.
    asked = {str(a["ref"]) for a in asks}
    for repo in sorted({str(a["ref"]).partition(":")[0] for a in asks}):
        for pair, amount in edge_currents(
            gn,
            repo,
            weights.local,
            weights.peer,
            weights.peer_blocked,
            weights.operator,
            workable=False,
        ).items():
            if pair[1] in asked:
                crossed[pair] += amount
    for e in edges:
        need, pre = (
            (e["target"], e["source"])
            if e["kind"] == "enables"
            else (e["source"], e["target"])
        )
        carried = crossed.get((ref(URIRef(need)), ref(URIRef(pre))), 0.0)
        if carried:
            e["current"] = round(carried, 4)
    # nemik:W119: a total order on everything drawn. rdflib iterates in hash order, and Python salts
    # str hashes per process, so without this every server start (and every rebuild after an
    # insertion) handed the layout the same graph in a different order, and dagre/cytoscape laid it
    # out differently: the view "jumped around" with no data change (operator 2026-09-28).
    nodes.sort(key=lambda n: n["id"])
    for item in nodes:
        item["blocked_on"] = sorted(item["blocked_on"])
    edges.sort(key=lambda e: (e["source"], e["target"], e["kind"]))
    # nemik:W317: each repo's red/amber/green from the declared thresholds, over `gn` like every number.
    from nemik.health import health, thresholds

    limits = thresholds()
    return {
        "nodes": nodes,
        "edges": edges,
        "inbound": blocks,
        "operator": asks,
        "findings": {r: [list(f) for f in fs] for r, fs in findings.items()},
        "health": {
            r: health(gn, r, limits)._asdict()
            for r in sorted({n["repo"] for n in nodes})
        },
        "ruler": ruler_table(edges, asks),
    }


def ruler_table(edges: list[dict], asks: list[dict]) -> dict[str, list[str]]:
    """nemik:W418: the ruler-sequence patterns the page draws, from mtools' generator (mtools:W1048).

    `motif[k]` is the order-k motif (one per halo scope, orders 0..3). `f[n]` is F(n), the pattern of
    the n-th line into one blocker; which lines a view shows is the page's choice, so it indexes this
    table rather than the server fixing each line's n. A line's n is at most the lines into its blocker
    or into an ask chip (one per category and repo), so the table runs to the larger of those.
    """
    from collections import Counter

    from mikemol.rulerseq import emit_f, morse_motif

    into = Counter(e["target"] for e in edges if e["kind"] == "waits")
    chips = Counter((a["category"], str(a["ref"]).partition(":")[0]) for a in asks)
    top = max([*into.values(), *chips.values(), 0])
    return {
        "motif": [morse_motif(k) for k in range(4)],
        "f": [
            emit_f([int(b) for b in reversed(f"{n:b}")]) if n else ""
            for n in range(top + 1)
        ],
    }


def handler(model: Model) -> type[BaseHTTPRequestHandler]:
    page = files("nemik.web").joinpath("index.html").read_bytes()
    vendor = files("nemik.web").joinpath("vendor")

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self.send(200, "text/html; charset=utf-8", page)
                return
            if self.path.startswith("/vendor/"):
                name = self.path.removeprefix("/vendor/")
                if name in VENDOR:
                    self.send(
                        200, "text/javascript", vendor.joinpath(name).read_bytes()
                    )
                else:
                    self.send(404, "text/plain", b"not found")
                return
            if (
                self.path != "/metrics"
            ):  # a scrape reports the model; it never drives a rebuild
                model.poke()
            if self.path in ("/wake", "/wake.json"):
                g = model.graph
                live, source = read_liveness(model.root, None)
                wake_body = {
                    "liveness": source,
                    "roster": roster(g, live),
                    "operator": operator_row(g),
                    "series": model.series_doc(),
                }
                self.send(
                    200,
                    "application/json",
                    json.dumps(wake_body, indent=1).encode(),
                )
            elif self.path in ("/operator", "/operator.json"):
                operator_body = json.dumps(model.doc["operator"], indent=1).encode()
                self.send(200, "application/json", operator_body)
            elif self.path.startswith("/inbound"):
                inbound_repo = (
                    self.path.removeprefix("/inbound").strip("/").removesuffix(".json")
                )
                doc = model.doc["inbound"]
                rows = [
                    b for b in doc if not inbound_repo or b["blocker"] == inbound_repo
                ]
                self.send(200, "application/json", json.dumps(rows, indent=1).encode())
            elif self.path.startswith("/goals/"):
                # nemik:W80: the W79 goal view, computed on the cached graph.
                from nemik.rank import goals, load_weights

                goals_repo = (
                    self.path.removeprefix("/goals/").strip("/").removesuffix(".json")
                )
                goals_body = goals(model.graph, goals_repo, load_weights())
                self.send(
                    200,
                    "application/json",
                    json.dumps(goals_body, indent=1).encode(),
                )
            elif self.path == "/metrics":
                self.send(200, "text/plain; version=0.0.4", model.metrics())
            elif self.path == "/series.json":
                series_body = json.dumps(model.series_doc(), indent=1).encode()
                self.send(200, "application/json", series_body)
            elif self.path == "/graph.json":
                self.send(200, "application/json", model.payload)
            elif self.path == "/graph.ttl":
                self.send(
                    200, "text/turtle", model.graph.serialize(format="turtle").encode()
                )
            else:
                self.send(404, "text/plain", b"not found")

        def send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: object) -> None:
            pass

    return H


def write_static(out: Path) -> list[Path]:
    """nemik:W169: the page and its scripts as files under `out`, every link relative, so the view
    works from any bucket subpath. Data files are W170's; the gate is W172's."""
    web = files("nemik.web")
    written = [out / "index.html"]
    (out / "vendor").mkdir(parents=True, exist_ok=True)
    page = web.joinpath("index.html").read_text()
    # nemik:W397: the page no longer has a Tools panel (W171 cut it here), so it is written as it is.
    written[0].write_text(page)
    for name in sorted(VENDOR):
        dst = out / "vendor" / name
        dst.write_bytes(web.joinpath("vendor").joinpath(name).read_bytes())
        written.append(dst)
    return written


def static_data(model: Model) -> dict[str, object]:
    """nemik:W170: every document the page fetches, computed once from one export, as
    {published path: document}. Only what the page reads is published: inbound/<repo>.json was
    planned, but the page never fetches it, so it stays off the public surface."""
    from nemik.rank import goals, load_weights

    model.refresh()
    g, live = model.graph, read_liveness(model.root, None)[0]
    docs: dict[str, object] = {
        "graph.json": model.doc,
        # The liveness *source* is a host path; the static view says only that it is a snapshot.
        "wake.json": {
            "liveness": "snapshot",
            "roster": roster(g, live),
            "operator": operator_row(g),
            # nemik:W671: luthen's series as a board, or board false with the reason; a withheld
            # card is not counted, and it names repos and states only.
            "series": model.series_doc(),
        },
    }
    weights = load_weights()
    for repo in sorted(
        {n["repo"] for n in model.doc["nodes"] if n["id"].startswith(BASE)}
    ):
        docs[f"goals/{repo}.json"] = goals(g, repo, weights)
    docs["history.json"] = history_doc(model.root, model.withheld)
    return docs


def history_doc(
    root: Path, withheld: frozenset[str] = frozenset()
) -> dict[str, list[dict[str, Any]]]:
    """nemik:W308: the project-manager's weekly roll-up per repo, from each repo's committed queue.

    Counts and days only: the roll-up row's `oldest_blocked` symbol is dropped, so nothing here names
    a waypoint, and a withheld waypoint (nemik:W309) is left out of every snapshot before counting.
    It needs git history, so only a host-side build has it (the pod has none).
    """
    from nemik.history import snapshots, weekly

    out: dict[str, list[dict[str, Any]]] = {}
    for repo, path in workstream_files(root, QUEUE):
        hide = {r.partition(":")[2] for r in withheld if r.partition(":")[0] == repo}
        snaps = [
            (
                at,
                {
                    **q,
                    "waypoints": [
                        w for w in q.get("waypoints", []) if w["symbol"] not in hide
                    ],
                },
            )
            for at, q in snapshots(path.parents[1])
        ]
        rows = weekly(snaps)
        out[repo] = [
            {k: v for k, v in r.items() if k != "oldest_blocked"} for r in rows
        ]
    return out


def build_static(
    root: Path,
    out: Path,
    withheld: Path | None,
    private: bool = False,
    exports: Path | None = None,
) -> list[Path]:
    """nemik:W153 (see _build_static), inside the same per-build scope the live server's document is
    built in (nemik:W412, W403): each graph indexed once and each flow solve answered once. The build
    ran outside it, so the goals, the pieces and the TRS feeds asked rdflib 1.09 M times for facts the
    index holds (a warm publish profiled at 94 s, a third of it in rank.goals)."""
    from nemik.index import indexed
    from nemik.salience import memo_audits

    with memo_audits(), indexed():
        return _build_static(root, out, withheld, private, exports)


def _build_static(
    root: Path,
    out: Path,
    withheld: Path | None,
    private: bool = False,
    exports: Path | None = None,
) -> list[Path]:
    """nemik:W153: the gated static view under `out`. Every check runs before anything is written,
    so a refused build leaves `out` untouched; the withheld list itself is never copied into it.

    nemik:W503: `private` is the pod's own build: nothing is withheld unless a list is given, and the
    files the live server answered beyond the public view are written too (see private_files).

    nemik:W634: with `exports`, each repo's own export (docs/withholding-at-source.md) also decides
    what leaves it, failing closed per repo: a repo with no export publishes none of its cards."""
    from nemik.manifest import unmanifested
    from nemik.withheld import apply, load

    refs = (
        frozenset() if private and withheld is None else load(withheld)
    )  # public fails closed
    if exports is not None:
        refs |= withheld_by_exports(root, exports)
    model = Model(root, refs, series=root / SERIES_FILE, series_max_age=SERIES_MAX_AGE)
    docs = apply(static_data(model), refs)
    if bad := [f for name, doc in docs.items() for f in unmanifested(name, doc)]:
        raise ValueError("unmanifested fields, refusing to publish: " + ", ".join(bad))
    # nemik:W415: graph.json's pieces, cut after the checks above from the document they checked,
    # so they hold nothing graph.json may not; graph.json stays until the page reads pieces (W416).
    from nemik.pieces import split

    for piece, cut in split(docs["graph.json"]).items():
        docs[f"graph/{piece}.json"] = cut
    # nemik:W440: the contract the published files keep, generated from the field manifest and listed in
    # hashes.json like the data, so a client sees when it changes
    from nemik.apischema import openapi, schema_path, schemas

    for pattern, schema in schemas().items():
        docs[schema_path(pattern)] = schema
    # nemik:W442: the read API, generated from the same schemas
    docs["openapi.json"] = openapi()
    written = write_static(out)
    # nemik:W414: hashes.json maps each published data path to the sha256 of its bytes, so a page
    # (W416) can refetch only the pieces that changed. Paths and digests only: nothing withheld.
    import hashlib

    # nemik:W449: each repo's Tracked Resource Set (W448) as Turtle, the form TRS readers consume; a
    # withheld card leaves both the base and the change log
    from nemik.trs import turtle
    from nemik.withheld import _id

    hidden = frozenset(_id(r) for r in refs)
    bodies = {name: json.dumps(doc, indent=1) for name, doc in docs.items()}
    repos = {str(n["repo"]) for n in docs["graph.json"]["nodes"] if n["repo"]}
    for repo in sorted(repos):
        feed = turtle(repo, model.graph, model.graph, hidden)
        for part in ("base", "changelog"):
            bodies[f"trs/{repo}/{part}.ttl"] = feed[part]
        # nemik:W354: the repo's cards as a read-only ForgeFed outbox (ActivityStreams JSON-LD)
        bodies[f"outbox/{repo}.jsonld"] = outbox(repo, model.graph, hidden)
    # nemik:W451: the OSLC discovery root, pointing at each repo's tracked resource set above
    from nemik.catalog import catalog

    bodies["catalog.ttl"] = catalog(sorted(repos)).serialize(format="turtle")
    hashes: dict[str, str] = {}
    for name, body in sorted(bodies.items()):
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body)
        hashes[name] = hashlib.sha256(body.encode()).hexdigest()
        written.append(dst)
    (out / "hashes.json").write_text(json.dumps(hashes, indent=1, sort_keys=True))
    written.append(out / "hashes.json")
    if private:
        written += private_files(model, out)
    return written


def private_files(model: Model, out: Path) -> list[Path]:
    """nemik:W503: what the live server answered beyond the public view, as files: /operator.json,
    /inbound.json and /inbound/<repo>.json (one per repo, empty when nothing waits on it), /graph.ttl,
    /metrics with the snapshot's own age gauge, and the source key the next publish compares. Never
    part of the public build: these name every waypoint's asks and blockers."""
    made: list[Path] = []

    def put(name: str, body: bytes) -> None:
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(body)
        made.append(dst)

    def dump(doc: object) -> bytes:
        return json.dumps(doc, indent=1).encode()

    rows = model.doc["inbound"]
    put("operator.json", dump(model.doc["operator"]))
    put("inbound.json", dump(rows))
    repos = {str(n["repo"]) for n in model.doc["nodes"] if n["repo"]}
    for repo in sorted(repos | {str(b["blocker"]) for b in rows}):
        put(f"inbound/{repo}.json", dump([b for b in rows if b["blocker"] == repo]))
    # N-Triples, which is Turtle with one triple per line: the same RDF a /graph.ttl reader parses, without
    # the grouping and sorting that made the Turtle serializer the costliest single write of the build
    put("graph.ttl", model.graph.serialize(format="nt").encode())
    gauge = (
        "# TYPE nemik_snapshot_published_seconds gauge\n"
        f"nemik_snapshot_published_seconds {time.time():.0f}\n"
    )
    put("metrics", model.metrics() + gauge.encode())
    return made


def fleet_key(root: Path) -> str:
    """The digest of every queue and ledger file's path and CONTENT now. Content, not mtime: an export
    that rewrites a file without changing it (luthen's does, every minute) is not a change, and a build
    costs real CPU (luthen-observability, nemik:W504: the builder rebuilds on a changed content hash)."""
    import hashlib

    digest = hashlib.sha256()
    for name in (QUEUE, LEDGER):
        for _, path in workstream_files(root, name):
            digest.update(str(path).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def publish(
    root: Path,
    base: Path,
    withheld: Path | None,
    keep: int = 3,
    exports: Path | None = None,
) -> Path | None:
    """nemik:W503: build a private snapshot under base/snap-<stamp>-<pid>/ and flip base/current to it
    with one atomic rename. The build runs in this short-lived process, so every byte of its graph is
    returned to the OS when it exits (nemik:W500: rebuilding in a long-lived process left ~20 MB of
    fragmented heap per build). Returns None when no queue or ledger changed since current/ was built.
    The last `keep` snapshots stay, so a request already reading one is not pulled out from under it."""
    from nemik import cachestore

    key = fleet_key(root)
    if exports is not None:  # nemik:W636: a changed export rebuilds the pod's view too
        key += "|exports:" + exports_key(exports)
    # nemik:W671: luthen's series board is baked into the view, so with a snapshot beside the queues
    # the view is rebuilt every ten minutes
    if (root / SERIES_FILE).exists():
        key += "|series:" + str(int(time.time()) // SERIES_REBUILD_S)
    live = base / "current" / "source-key"
    if live.exists() and live.read_text() == key:
        return None
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    snap = base / f"snap-{stamp}-{os.getpid()}"
    cachestore.load(
        base / ".cache"
    )  # nemik:W518: start warm, as the long-lived server was
    try:
        build_static(root, snap, withheld, private=True, exports=exports)
        (snap / "source-key").write_text(key)
    except BaseException:
        shutil.rmtree(snap, ignore_errors=True)
        raise
    cachestore.save(base / ".cache")
    link = base / f".current-{os.getpid()}"
    link.unlink(missing_ok=True)
    link.symlink_to(snap.name)
    os.replace(link, base / "current")
    for old in sorted(p for p in base.glob("snap-*") if p.is_dir())[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    return snap


class _Options(argparse.Namespace):
    """The parsed command line, typed, so each option reads as its own type."""

    root: Path
    bind: str
    port: int
    static: Path | None
    withheld: Path | None
    withheld_max_age: int
    runs: Path | None
    series: Path | None
    series_max_age: int
    exports: Path | None
    publish: Path | None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="nemik-serve", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8750)
    ap.add_argument(
        "--static",
        type=Path,
        metavar="OUT",
        help="write the view as static files under OUT and exit (nemik:W153); needs --withheld",
    )
    ap.add_argument(
        "--withheld",
        type=Path,
        metavar="FILE",
        help="luthen's withheld list (v1); required with --static, a missing file fails the build",
    )
    ap.add_argument(
        "--withheld-max-age",
        type=int,
        default=0,
        metavar="SECONDS",
        help="refuse the withheld list when its as_of is older than SECONDS (0: no limit); "
        "luthen restamps it every minute, so 900 is a real stop (nemik:W647)",
    )
    ap.add_argument(
        "--runs",
        type=Path,
        metavar="DIR",
        help="the live server only: luthen's published run logs, DIR/<stream>.jsonl, read as "
        "prov:Activity rows into the graph (nemik:W565)",
    )
    ap.add_argument(
        "--series",
        type=Path,
        metavar="FILE",
        help="the live server only: luthen's loop and token snapshot (luthen-series.json), served "
        "as /series.json; a missing, unversioned or stale file serves no board (nemik:W670)",
    )
    ap.add_argument(
        "--series-max-age",
        type=int,
        default=900,
        metavar="SECONDS",
        help="refuse the series snapshot when its as_of is older than SECONDS (default 900)",
    )
    ap.add_argument(
        "--exports",
        type=Path,
        metavar="DIR",
        help="with --static or --publish: the repos' own exports, DIR/<repo>.json (version 2); a "
        "repo with no export publishes none of its cards (nemik:W634, W636)",
    )
    ap.add_argument(
        "--publish",
        type=Path,
        metavar="BASE",
        help="build a private snapshot under BASE and flip BASE/current to it atomically, then exit "
        "(nemik:W503); skipped when nothing changed; --withheld is optional (the pod is not the "
        "public view)",
    )
    args = ap.parse_args(argv, namespace=_Options())
    if args.withheld is not None and args.withheld_max_age:
        try:
            require_fresh(args.withheld, args.withheld_max_age, time.time())
        except ValueError as e:
            sys.stderr.write(f"ERROR: {e}\n")
            raise SystemExit(2) from e
    if args.publish:
        try:
            snap = publish(args.root, args.publish, args.withheld, exports=args.exports)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            raise SystemExit(2) from e
        print(snap if snap else "unchanged")
        return
    if args.static:
        try:
            for path in build_static(
                args.root, args.static, args.withheld, exports=args.exports
            ):
                print(path)
        except (
            ValueError
        ) as e:  # WithheldError, an unmanifested field, missing page markers
            print(f"ERROR: {e}", file=sys.stderr)
            raise SystemExit(2) from e
        return
    model = Model(
        args.root,
        runs=args.runs,
        series=args.series,
        series_max_age=args.series_max_age,
    )
    ThreadingHTTPServer((args.bind, args.port), handler(model)).serve_forever()


if __name__ == "__main__":
    main()
