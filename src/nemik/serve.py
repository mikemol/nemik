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
import threading
import time
from importlib.metadata import PackageNotFoundError, version
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import BASE, NEMIK, OPERATOR, OSLC_CM, bind, ledger_graph
from nemik.blocks import inbound, operator_asks, ref
from nemik.wake import operator_row, read_liveness, roster
from nemik.check import LEDGER, QUEUE, default_root, survey, workstream_files


VENDOR = {"cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.js"}


class Model:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.key: tuple = ()
        self.graph = bind(Graph())
        self.payload = b"{}"
        self.doc: dict = {"operator": [], "inbound": []}  # parsed once per rebuild, shared by requests
        self.rebuilds = 0
        self.rebuild_cpu = 0.0
        self.nodes = self.edges = self.workstreams = 0
        # ThreadingHTTPServer: refresh() runs on every request (nemik:W19). Without this lock,
        # several requests arriving as a queue file changes (e.g. luthen's once-a-minute export)
        # each redo the full survey()+SHACL rebuild concurrently -- wasted CPU under the GIL that
        # can starve the accept loop, not just a duplicated cache miss.
        self._lock = threading.Lock()

    def sources(self) -> list[Path]:
        return [p for name in (QUEUE, LEDGER) for _, p in workstream_files(self.root, name)]

    def refresh(self) -> None:
        key = tuple((str(p), p.stat().st_mtime_ns) for p in self.sources())
        if key == self.key:
            return
        with self._lock:
            if key == self.key:  # someone else rebuilt while we waited for the lock
                return
            cpu0 = time.process_time()
            g, findings = bind(Graph()), {}
            for repo, qg, fs in survey(self.root):
                findings[repo] = fs
                if qg is not None:
                    g += qg
            for repo, path in workstream_files(self.root, LEDGER):
                lg, _ = ledger_graph(repo, path)
                g += lg
            self.graph, self.key = g, key
            self.rebuilds += 1
            self.rebuild_cpu = time.process_time() - cpu0
            doc = to_json(g, findings)
            self.nodes, self.edges, self.workstreams = len(doc["nodes"]), len(doc["edges"]), len(findings)
            self.doc, self.payload = doc, json.dumps(doc).encode()

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
        return "\n".join([
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
            "",
        ]).encode()


def local(term) -> str:
    """The last segment of a nemik:/oslc IRI: after '#', '/', or the urn:nemik: prefix."""
    return str(term).removeprefix("urn:nemik:").rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def to_json(g: Graph, findings: dict) -> dict:
    effort: dict[str, Counter] = defaultdict(Counter)
    last: dict[str, str] = {}
    for act in g.subjects(RDF.type, PROV.Activity):
        cls = str(g.value(act, NEMIK.effortClass))
        stamp = str(g.value(act, PROV.startedAtTime) or "")
        for wp in g.objects(act, PROV.used):
            effort[str(wp)][cls] += 1
            last[str(wp)] = max(last.get(str(wp), ""), stamp)
    nodes, edges = [], []
    for kind, cls in (("waypoint", OSLC_CM.ChangeRequest), ("dropped", NEMIK.Dropped)):
        for n in g.subjects(RDF.type, cls):
            state = local(g.value(n, OSLC_CM.state)).lower() if kind == "waypoint" else "dropped"
            nodes.append({
                "id": str(n),
                "repo": local(g.value(n, NEMIK.workstream)),
                "symbol": str(g.value(n, NEMIK.symbol)),
                "title": str(g.value(n, DCTERMS.title) or ""),
                "state": state,
                "blocked_on": [str(o) for o in g.objects(n, NEMIK.blockedOn)],
                "blocked_kind": str(g.value(n, NEMIK.blockedKind) or ""),
                "effort": dict(sorted(effort.get(str(n), {}).items())),
                "last_activity": last.get(str(n), ""),
                "minted_during": str(g.value(n, NEMIK.mintedDuring) or ""),
                "caused_by": str(g.value(n, PROV.wasInformedBy) or ""),
            })
    for s, _, o in g.triples((None, NEMIK.enables, None)):
        edges.append({"source": str(s), "target": str(o), "kind": "enables"})
    # A block on another workstream ends at the blocker's waypoint that claims it, or at an
    # "unclaimed" placeholder inside the blocker's box, never at a bare repo label.
    blocks = inbound(g)
    # One (blocked, blocker) pair can have several inbound rows (linux-sources:W40 waits on the mtools
    # session AND mtools:W24 AND mtools:W46). Keeping only the last row made which claims got drawn
    # depend on hash order (nemik:W119), so the claims are merged.
    by_blocked: dict[tuple[str, str], dict] = {}
    for b in blocks:
        m = by_blocked.setdefault((b["blocked"], b["blocker"]), {**b, "claimed_by": []})
        m["claimed_by"] = sorted(set(m["claimed_by"]) | set(b["claimed_by"]))
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
                edges.append({"source": str(s), "target": f"{BASE}{repo}/{sym}", "kind": "waits"})
        else:
            ask = f"ask:{b['blocked']}@{b['blocker']}"
            nodes.append({
                "id": ask, "repo": b["blocker"], "symbol": "?", "state": "unclaimed",
                "title": f"nothing in {b['blocker']} claims {b['blocked']} yet",
                "blocked_on": b["blocked_on"], "blocked_kind": "", "effort": {},
                "last_activity": "", "minted_during": "", "caused_by": "", "cite": "",
                "for": b["blocked"],
            })
            edges.append({"source": str(s), "target": ask, "kind": "waits"})
    asks = operator_asks(g)
    for a in asks:
        edges.append({"source": f"{BASE}{a['ref'].replace(':', '/', 1)}", "target": f"operator:{a['category']}",
                      "kind": "waits"})
    # nemik:W56: an edge whose upstream end is done no longer holds anything back. For `enables`
    # that end is the source; for `waits` it is the target. open_blockers counts what still does.
    done = {n["id"] for n in nodes if n["state"] == "done"}
    # Distinct upstream items, since W3 enables W1 and W1 waits on W3 name one blocker.
    open_blockers: dict[str, set] = defaultdict(set)
    for e in edges:
        up, down = (e["source"], e["target"]) if e["kind"] == "enables" else (e["target"], e["source"])
        e["satisfied"] = up in done
        if not e["satisfied"]:
            open_blockers[down].add(up)
    for n in nodes:
        n["open_blockers"] = len(open_blockers.get(n["id"], ()))
        if n["id"].startswith(BASE):
            n["cite"] = ref(URIRef(n["id"]))
    # nemik:W135: each ready waypoint's place in its repo's composed nemik-rank order (0 = work it
    # first), so the page can lay out a rank-ordered forest without re-deriving the ranking.
    from nemik.rank import load_composition, load_weights, rank

    weights, comp = load_weights(), load_composition()
    by_id = {n["id"]: n for n in nodes}
    for repo in sorted({n["repo"] for n in nodes if n["state"] == "ready"}):
        for i, r in enumerate(rank(g, repo, weights, comp)):
            if n := by_id.get(f"{BASE}{repo}/{r['symbol']}"):
                n["rank_pos"], n["band"] = i, r["band_name"]
    # nemik:W119: a total order on everything drawn. rdflib iterates in hash order, and Python salts
    # str hashes per process, so without this every server start (and every rebuild after an
    # insertion) handed the layout the same graph in a different order, and dagre/cytoscape laid it
    # out differently: the view "jumped around" with no data change (operator 2026-09-28).
    nodes.sort(key=lambda n: n["id"])
    for n in nodes:
        n["blocked_on"] = sorted(n["blocked_on"])
    edges.sort(key=lambda e: (e["source"], e["target"], e["kind"]))
    return {
        "nodes": nodes,
        "edges": edges,
        "inbound": blocks,
        "operator": asks,
        "findings": {r: [list(f) for f in fs] for r, fs in findings.items()},
    }


def handler(model: Model) -> type[BaseHTTPRequestHandler]:
    page = files("nemik.web").joinpath("index.html").read_bytes()
    vendor = files("nemik.web").joinpath("vendor")

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server's name
            if self.path in ("/", "/index.html"):
                self.send(200, "text/html; charset=utf-8", page)
                return
            if self.path.startswith("/vendor/"):
                name = self.path.removeprefix("/vendor/")
                if name in VENDOR:
                    self.send(200, "text/javascript", vendor.joinpath(name).read_bytes())
                else:
                    self.send(404, "text/plain", b"not found")
                return
            if self.path != "/metrics":  # a scrape reports the model; it never drives a rebuild
                model.poke()
            if self.path in ("/wake", "/wake.json"):
                g = model.graph
                live, source = read_liveness(model.root, None)
                body = {"liveness": source, "roster": roster(g, live), "operator": operator_row(g)}
                self.send(200, "application/json", json.dumps(body, indent=1).encode())
            elif self.path in ("/operator", "/operator.json"):
                body = json.dumps(model.doc["operator"], indent=1).encode()
                self.send(200, "application/json", body)
            elif self.path.startswith("/inbound"):
                repo = self.path.removeprefix("/inbound").strip("/").removesuffix(".json")
                doc = model.doc["inbound"]
                body = [b for b in doc if not repo or b["blocker"] == repo]
                self.send(200, "application/json", json.dumps(body, indent=1).encode())
            elif self.path.startswith("/cmd/"):
                # nemik:W81: a read-only CLI's exact output over the cached graph.
                from urllib.parse import parse_qs, urlparse

                from nemik.tools import run
                u = urlparse(self.path)
                repo = (parse_qs(u.query).get("repo") or [None])[0]
                try:
                    code, out = run(u.path.removeprefix("/cmd/"), model.graph, str(model.root), repo)
                except ValueError as e:
                    self.send(400, "text/plain; charset=utf-8", str(e).encode())
                    return
                self.send(200, "text/plain; charset=utf-8", f"# exit {code}\n{out}".encode())
            elif self.path.startswith("/goals/"):
                # nemik:W80: the W79 goal view, computed on the cached graph.
                from nemik.rank import goals, load_weights
                repo = self.path.removeprefix("/goals/").strip("/").removesuffix(".json")
                body = goals(model.graph, repo, load_weights())
                self.send(200, "application/json", json.dumps(body, indent=1).encode())
            elif self.path == "/metrics":
                self.send(200, "text/plain; version=0.0.4", model.metrics())
            elif self.path == "/graph.json":
                self.send(200, "application/json", model.payload)
            elif self.path == "/graph.ttl":
                self.send(200, "text/turtle", model.graph.serialize(format="turtle").encode())
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


def main() -> None:
    ap = argparse.ArgumentParser(prog="nemik-serve", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8750)
    args = ap.parse_args()
    ThreadingHTTPServer((args.bind, args.port), handler(Model(args.root))).serve_forever()


if __name__ == "__main__":
    main()
