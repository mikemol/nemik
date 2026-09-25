"""nemik-serve: a read-only web view of the merged workstream graph.

    /             the dependency view (static page; draws /graph.json)
    /graph.json   waypoints, enables edges, and per-waypoint effort by class, for the page
    /graph.ttl    the merged RDF graph (OSLC CM ChangeRequests + PROV ledger activities)
    /vendor/*     cytoscape, dagre, cytoscape-dagre, vendored so the page never leaves the host
    /metrics      Prometheus text: graph size, last rebuild cost, build info

The graph is rebuilt only when a queue or ledger file changes (mtime key), so a page poll costs
a stat walk, not a SHACL pass.
"""

from __future__ import annotations

import argparse
import json
import time
from importlib.metadata import PackageNotFoundError, version
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from rdflib import RDF, Graph
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import NEMIK, OPERATOR, OSLC_CM, bind, ledger_graph
from nemik.check import LEDGER, QUEUE, default_root, survey, workstream_files


VENDOR = {"cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.js"}


class Model:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.key: tuple = ()
        self.graph = bind(Graph())
        self.payload = b"{}"
        self.rebuilds = 0
        self.rebuild_cpu = 0.0
        self.nodes = self.edges = self.workstreams = 0

    def sources(self) -> list[Path]:
        return [p for name in (QUEUE, LEDGER) for _, p in workstream_files(self.root, name)]

    def refresh(self) -> None:
        key = tuple((str(p), p.stat().st_mtime_ns) for p in self.sources())
        if key == self.key:
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
        self.payload = json.dumps(doc).encode()

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
                "effort": dict(effort.get(str(n), {})),
                "last_activity": last.get(str(n), ""),
                "minted_during": str(g.value(n, NEMIK.mintedDuring) or ""),
                "caused_by": str(g.value(n, PROV.wasInformedBy) or ""),
            })
    for s, _, o in g.triples((None, NEMIK.enables, None)):
        edges.append({"source": str(s), "target": str(o), "kind": "enables"})
    for s, _, o in g.triples((None, NEMIK.waitsFor, None)):
        if o == OPERATOR:
            target = "operator"
        elif (o, RDF.type, NEMIK.Workstream) in g:
            target = "repo:" + local(o)
        else:
            target = str(o)
        edges.append({"source": str(s), "target": target, "kind": "waits"})
    return {
        "nodes": nodes,
        "edges": edges,
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
            model.refresh()
            if self.path == "/metrics":
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
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8750)
    args = ap.parse_args()
    ThreadingHTTPServer((args.bind, args.port), handler(Model(args.root))).serve_forever()


if __name__ == "__main__":
    main()
