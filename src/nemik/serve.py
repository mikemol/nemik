# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-serve: a read-only web view of the merged workstream graph.

    /             the dependency view (static page; draws /graph.json)
    /graph.json   waypoints, enables edges, and per-waypoint effort by class, for the page
    /graph.ttl    the merged RDF graph (OSLC CM ChangeRequests + PROV ledger activities)
    /vendor/*     cytoscape, dagre, cytoscape-dagre, vendored so the page never leaves the host
    /metrics      Prometheus text: graph size, last rebuild cost, build info
    /operator     open waypoints blocked on the operator: needs-you / answered / condition /
    unstated /wake         blocked-on workstreams with their liveness: which must be woken, and for
    what /inbound[/<repo>]  open waypoints waiting on <repo> (or anyone), each with the blocker's
                  claiming waypoints: what an agent reads to learn "I am the block, and on what"

The graph is rebuilt only when a queue or ledger file changes (mtime key), so a page poll costs
a stat walk, not a SHACL pass.
"""

from __future__ import annotations

import argparse
import json
import operator
import os
import shutil
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS, PROV

from nemik.adapter import BASE, NEMIK, OPERATOR, OSLC_CM, bind, ledger_graph
from nemik.blocks import inbound, operator_asks, ref
from nemik.buildcost import (
    build_cost_lines,
    bytes_of,
    labels_of,
    peak_kib_of,
    swap_kib_of,
)
from nemik.cardseries import card_lines
from nemik.check import (
    LEDGER,
    QUEUE,
    Finding,
    blocked_rows,
    default_root,
    finding_lines,
    integrity_text,
    ready_neither_text,
    unmanifested_text,
    workstream_files,
)
from nemik.check import survey as checked_survey
from nemik.collapse import collapse, paths
from nemik.collapse import lines as collapse_lines
from nemik.critical import critical_doc
from nemik.exportwire import exports_key, withheld_by_exports
from nemik.floorasks import floor_asks, unresolved
from nemik.histdocs import STALE_HOURS, decode, file_name, wrap
from nemik.history import oldest_rows
from nemik.hostroot import HostRow, read_document, stale
from nemik.landings import read_document as read_landings
from nemik.landings import series as landing_series
from nemik.letters import report as letters_report
from nemik.luthenseries import board, load
from nemik.outbox import outbox
from nemik.overlaps import overlaps
from nemik.pacepublish import metric_lines, read_pace, readable_lines
from nemik.pacing import limits, paces
from nemik.queuerows import fleet_queues
from nemik.roundcli import bindings_of
from nemik.roundfile import ROUND_FILE
from nemik.roundgauges import round_board
from nemik.runlogs import runs_graph
from nemik.stackable import manifest
from nemik.starved import days_limit, starved_fleet
from nemik.wake import operator_row, read_liveness, roster
from nemik.withheldage import require_fresh

# nemik:W783: the server never starts a process, so its survey skips the gate marks that ask
# mikemol-commit which cards a commit stack names (a spawn, for the CLIs beside the committer).
survey = partial(checked_survey, gate="")


def queue_doc(graph: Graph) -> dict[str, object]:
    """Build every repo's ready cards as a queue, in work order (nemik:W931).

    Args:
        graph: The merged queue graph, less what luthen withholds.

    Returns:
        {"as_of": the instant waits are measured to, "queues": {repo: [{place, cite, title, weight,
        band, waited_days, overtaken_by}, ...]}}.

    """
    now = datetime.now(UTC)
    queues = fleet_queues(graph, [], now)
    return {
        "as_of": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "queues": {
            repo: [row._asdict() for row in rows] for repo, rows in queues.items()
        },
    }


def check_report(name: str, graph: Graph, root: Path) -> str | None:
    """Give one of nemik-check's report modes as the CLI words it (nemik:W795, W796).

    Args:
        name: "ready-neither", "unmanifested", "integrity", "letters" or "fold".
        graph: The merged queue graph the last rebuild left.
        root: The fleet root, for the reports that read the queue files.

    Returns:
        The report's text, or None for a name that is no report.

    """
    if name == "ready-neither":
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return ready_neither_text(root, None, now)
    if name == "unmanifested":
        return unmanifested_text(graph)
    if name == "integrity":
        return integrity_text(graph, root)
    if name in {"letters", "fold"}:
        # nemik:W862, W863: the inbox report as --letters and --fold print it; the writing mode
        # (--apply) is not served, only the plan it would carry out.
        known = {repo for repo, _ in workstream_files(root, QUEUE)}
        return "\n".join(letters_report(root, known, name == "fold")[0])
    return None


if TYPE_CHECKING:
    from collections.abc import Callable

    from nemik.blocks import AskRow

VENDOR = {"cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.js"}
# nemik:W801: the page's own files beside index.html (nemik:W799 splits it by concern): the
# stylesheet and the script modules, each served at its name and copied by the static build when
# it exists. A name is listed here before its file lands, so a file nobody listed is never served.
PAGE_FILES = {
    "style.css": "text/css; charset=utf-8",
    "graph.js": "text/javascript; charset=utf-8",
    "cards.js": "text/javascript; charset=utf-8",
    "panels.js": "text/javascript; charset=utf-8",
    "queue.js": "text/javascript; charset=utf-8",
    "viewstate.js": "text/javascript; charset=utf-8",
    "render.js": "text/javascript; charset=utf-8",
    # nemik:W820: the Python core compiled to wasm64 (docs/wasm-pipeline.md) and the loader that
    # supplies its runtime; core.wasm is built by tools/build_wasm.sh and committed with its hash
    "wasm.js": "text/javascript; charset=utf-8",
    "core.wasm": "application/wasm",
}


def page_file(name: str, web: Path | None = None) -> bytes | None:
    """Read one of the page's own files out of the web directory (nemik:W801).

    Args:
        name: A file name; only those in PAGE_FILES are read.
        web: The directory holding index.html; the package's own when not given.

    Returns:
        The file's bytes, or None for an unlisted name or a listed file not there yet.

    """
    here = Path(str(files("nemik.web"))) if web is None else web
    if name not in PAGE_FILES or not (here / name).is_file():
        return None
    return (here / name).read_bytes()


# nemik:W671: luthen's loop snapshot sits beside the queues in the export (as withheld.json and
# liveness.json do); a published view reads it, refusing one older than SERIES_MAX_AGE, and is
# rebuilt every SERIES_REBUILD_S although no queue changed, since the board is baked in.
SERIES_FILE = "luthen-series.json"
# nemik:W949: the wait activities nemik-hostroot --log-activities writes on the host, put beside the
# queues like the series file; each repo's outbox appends its own, and a view without it says so.
LOG_FILE = "log-activities.json"
# nemik:W978: the commit landings nemik-hostroot --landings writes, beside the queues like the
# log file; the pod's private build publishes the board from it, so the builder needs no flag.
LANDINGS_FILE = "landings.json"
SERIES_MAX_AGE = 900
SERIES_REBUILD_S = 600


def check_board(findings: dict[str, list[Finding]]) -> dict[str, object]:
    """Word the fleet survey the way nemik-check prints it (nemik:W784).

    Args:
        findings: Each repo's findings, as the server's last rebuild left them.

    Returns:
        {"lines": nemik-check's lines, "digest": nemik-check --digest's, "failed": how many repos
        violate or are unreadable}; the wording is check.finding_lines, the CLI's own.

    """
    lines: list[str] = []
    digest: list[str] = []
    failed = 0
    for repo in sorted(findings):
        said, bad = finding_lines(repo, findings[repo], digest=False)
        brief, _ = finding_lines(repo, findings[repo], digest=True)
        lines.extend(said)
        digest.extend(brief)
        failed += bad
    return {"lines": lines, "digest": digest, "failed": failed}


def hostroot_board(path: Path | None, now: str) -> dict[str, object]:
    """Build the host-root board from nemik-hostroot's file (nemik:W780).

    Args:
        path: The file, or None when the server was not given one.
        now: The current time, an ISO stamp, against which staleness is judged.

    Returns:
        {"host": True, "as_of", "stale", "rows": [...]}, each row its id, state, waitsFor, gate,
        reading, as_of and whether it is stale; or {"host": False, "why": ...} when there is no
        file or it cannot be read: no board, never a guessed one.

    """
    if path is None:
        return {"host": False, "why": "no --hostroot file"}
    try:
        as_of, rows = read_document(path.read_text(encoding="utf-8"))
    except OSError:
        return {"host": False, "why": "no document"}  # never a host path
    except ValueError as error:
        return {"host": False, "why": str(error)}
    shown = [
        {
            "id": row.ident,
            "state": row.state,
            "waitsFor": row.waits_for,
            "gate": row.gate,
            "reading": row.reading,
            "as_of": row.as_of,
            "stale": stale(row, now),
        }
        for row in rows
    ]
    return {
        "host": True,
        "as_of": as_of,
        "stale": stale(HostRow("", "", as_of), now),
        "rows": shown,
    }


# the documents one Model.doc_for answers, by route: the boards the host writes files for
# (nemik:W780, W751) and the longest chain, whose answer nemik-critical --json shares (nemik:W786)
# nemik:W853: how many of the oldest open cards /oldest.json lists.
OLDEST_SHOWN = 25

DOC_ROUTES = [
    "/hostroot.json",
    "/oldest.json",
    "/collapse.json",
    "/series.json",
    "/check.json",
    "/landings.json",
    "/critical.json",
    "/starved.json",
    "/queue.json",
    "/overlaps.json",
    "/pacing.json",
    "/floor-asks.json",
]


def landings_board(path: Path | None, now: str) -> dict[str, object]:
    """Build the commit-landings board from nemik-hostroot --landings' file (nemik:W751).

    Args:
        path: The file, or None when the server was not given one.
        now: The current time, an ISO stamp, against which staleness is judged.

    Returns:
        {"host": True, "as_of", "stale", "series": {repo: [gate_s, ...]}, "landings": [...]}, the
        landings oldest first with repo, sha, card, gate_s and when; or {"host": False, "why": ...}
        when there is no file or it cannot be read: no board, never a guessed one.

    """
    if path is None:
        return {"host": False, "why": "no --landings file"}
    try:
        as_of, rows = read_landings(path.read_text(encoding="utf-8"))
    except OSError:
        return {"host": False, "why": "no document"}  # never a host path
    except ValueError as error:
        return {"host": False, "why": str(error)}
    shown = [
        {
            "repo": row.repo,
            "sha": row.sha,
            "card": row.card,
            "gate_s": row.gate_s,
            "when": row.when,
        }
        for row in rows
    ]
    return {
        "host": True,
        "as_of": as_of,
        "stale": stale(HostRow("", "", as_of), now),
        "series": landing_series(rows),
        "landings": shown,
    }


PACE_FILE = "ratchet-pace.json"


def pace_board(path: Path) -> tuple[dict[str, object], list[str]]:
    """Build the ratchet pace board and its gauges from the pace run's file (nemik:W990).

    Args:
        path: The file ratchetpace's run writes beside the queues.

    Returns:
        ({"host": True, "as_of", "window", "rows"}, the gauge lines), or ({"host": False, "why"},
        the readable gauge at 0) when there is no file or it cannot be read: no board, never a
        guessed one, and never no gauge at all (nemik:W1051): a ratchet whose gauges vanished
        read as no longer behind, so a failed read says so.

    """
    try:
        as_of, window, rows = read_pace(path.read_text(encoding="utf-8"))
    except OSError:
        # never a host path
        return {"host": False, "why": "no document"}, readable_lines(0)
    except ValueError as error:
        return {"host": False, "why": str(error)}, readable_lines(0)
    shown = [
        {
            "repo": repo,
            "ratchet": ratchet,
            "state": state,
            "observed": seen,
            "required": owed,
        }
        for repo, ratchet, state, seen, owed in rows
    ]
    board: dict[str, object] = {
        "host": True,
        "as_of": as_of,
        "window": window,
        "rows": shown,
    }
    return board, [*readable_lines(1), *metric_lines(rows, as_of)]


class Model:
    """The live view's state: the surveyed graph and its JSON, rebuilt when a source moves."""

    def __init__(
        self,
        root: Path,
        withheld: frozenset[str] = frozenset(),
        runs: Path | None = None,
        series: Path | None = None,
        series_max_age: int = 900,
    ) -> None:
        """Set up an empty model over one root; the first refresh builds the graph.

        Args:
            root: the workspace root whose queues and ledgers are surveyed.
            withheld: refs kept out of every published number.
            runs: luthen's published run logs, read as activity rows when given.
            series: luthen's loop and token snapshot, read per request when given.
            series_max_age: seconds after which the series snapshot is refused.

        """
        self.root = root
        # nemik:W780: the host-root frontier nemik-hostroot writes on the host (host-root.json),
        # set by main when given; read per request so its age is judged against the clock.
        self.hostroot: Path | None = None
        # nemik:W751: mikemol-commit's landings, written by nemik-hostroot --landings.
        self.landings: Path | None = None
        # nemik:W854: the history documents nemik-history --publish writes on the host.
        self.history_dir: Path | None = None
        # nemik:W784: each repo's findings as the last rebuild left them, worded by check_board.
        self.findings: dict[str, list[Finding]] = {}
        # nemik:W670: luthen's loop and token snapshot (luthen-series.json), read per request so its
        # age is judged against the clock, never against the last rebuild.
        self.series = series
        self.series_max_age = series_max_age
        # nemik:W565: luthen's published run logs (runs/<stream>.jsonl), read as prov:Activity rows
        # into the graph when a directory is given.
        self.runs = runs
        # nemik:W309: refs luthen withholds from the public view. They are kept out of every NUMBER
        # the view publishes (salience, edge current, history counts), not only out of the node
        # list.
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
        # nemik:W399: the last rebuild's CPU seconds per phase (parse, annotate, shacl,
        # fleet_checks, ledger, document), so the phase that dominates is measured, not guessed.
        self.phases: dict[str, float] = {}
        self.nodes = self.edges = self.workstreams = 0
        # ThreadingHTTPServer: refresh() runs on every request (nemik:W19). Without this lock,
        # several requests arriving as a queue file changes (e.g. luthen's once-a-minute export)
        # each redo the full survey()+SHACL rebuild concurrently -- wasted CPU under the GIL that
        # can starve the accept loop, not just a duplicated cache miss.
        self._lock = threading.Lock()

    def sources(self) -> list[Path]:
        """List the files whose change rebuilds the view: every queue and ledger, and the run logs.

        Returns:
            The queue and ledger paths under the root, plus each run log when --runs is given.

        """
        found = [
            p for name in (QUEUE, LEDGER) for _, p in workstream_files(self.root, name)
        ]
        if self.runs is not None:  # nemik:W565: a changed run log rebuilds the view too
            found += sorted(self.runs.glob("*.jsonl"))
        return found

    def refresh(self) -> None:
        """Rebuild the graph, findings and JSON document when a source file has moved.

        The rebuild runs under a lock, so concurrent requests do not each redo it, and it records
        the CPU seconds per phase. Nothing changes when the sources' mtimes match the last key.
        """
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
            self.findings = findings
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
        shown: dict[str, object] = {"board": True}
        shown.update(board(snap, ready))
        return shown

    def check_reply(self, path: str) -> tuple[int, str, bytes]:
        """Answer GET /check/<report>.json with the report as nemik-check words it (nemik:W795).

        Returns:
            (status, content type, body): the report as JSON, or 404 for a name that is none.

        """
        name = path.removeprefix("/check/").removesuffix(".json")
        said = check_report(name, self.graph, self.root)
        if said is None:
            return 404, "text/plain", b"no such report\n"
        body: dict[str, str] = {"report": name, "text": said}
        return 200, "application/json", json.dumps(body, indent=1).encode()

    def check_doc(self) -> dict[str, object]:
        """Give the fleet survey as nemik-check words it (nemik:W784).

        Returns:
            check_board's lines, digest and failed count over the last rebuild's findings.

        """
        return check_board(self.findings)

    def hostroot_doc(self) -> dict[str, object]:
        """Build the host-root board from nemik-hostroot's file (nemik:W780).

        Returns:
            {"host": True, "as_of", "stale", "rows": [...]}, each row its id, state, waitsFor,
            gate, reading, as_of and whether it is stale; or {"host": False, "why": ...} when
            there is no file or it cannot be read: no board, never a guessed one.

        """
        return hostroot_board(
            self.hostroot, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

    def landings_doc(self) -> dict[str, object]:
        """Build the commit-landings board from nemik-hostroot --landings' file (nemik:W751).

        Returns:
            {"host": True, "as_of", "stale", "series", "landings"}; or {"host": False, "why": ...}
            when there is no file or it cannot be read: no board, never a guessed one.

        """
        return landings_board(
            self.landings, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )

    def critical_json(self) -> dict[str, object]:
        """Build the longest chain and the cycles over the graph, less what luthen withholds.

        Returns:
            What nemik-critical --json prints (nemik:W786).

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        return critical_doc(g)

    def starved_json(self) -> dict[str, object]:
        """Build the ready cards overtaken by newer ones for longer than the declared age.

        Returns:
            {"days": the declared age, "starved": [{cite, waited_days, overtaken_by}, ...]}, the
            rows nemik-starved --json prints, over the graph less what luthen withholds.

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        days = days_limit()
        found = starved_fleet(g, [], datetime.now(UTC), days)
        return {"days": days, "starved": [s._asdict() for s in found]}

    def queue_json(self) -> dict[str, object]:
        """Build every repo's ready cards as a queue (nemik:W931), over the graph less the withheld.

        Returns:
            queue_doc's document.

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        return queue_doc(g)

    def overlaps_json(self) -> dict[str, object]:
        """Build the work tags more than one live card touches, as nemik-overlaps finds them.

        The claim holders the command appends come from a spawned mikemol-membudget, which the
        server never starts, so they are left out.

        Returns:
            {"overlaps": {tag: [cards]}, "cross": the same for tags shared across repos}, over the
            graph less what luthen withholds.

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        return {"overlaps": overlaps(g), "cross": overlaps(g, cross=True)}

    def pacing_json(self) -> dict[str, object]:
        """Build each repo's new cards against the declared rate and burst, as nemik-pacing does.

        Returns:
            {"rate", "burst", "days", "paces": [{repo, arrivals, overdraft, level}, ...]}, the most
            over first, over the graph less what luthen withholds.

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        rate, burst, days = limits()
        found = paces(g, datetime.now(UTC), rate, burst, days)
        return {
            "rate": rate,
            "burst": burst,
            "days": days,
            "paces": [p._asdict() for p in found],
        }

    def floor_asks_json(self) -> dict[str, object]:
        """Build whether the summit floor asks point at live waypoints, as nemik-floor-asks does.

        Returns:
            {"asks": how many floor entries carry a waypoint, "unresolved": [{key, pointer, why}]}
            from <root>/summit/floor; no floor directory is no asks.

        """
        floor = self.root / "summit" / "floor"
        bad = unresolved(self.root, floor)
        return {
            "asks": len(floor_asks(floor)),
            "unresolved": [
                {"key": key, "pointer": ptr, "why": why} for key, ptr, why in bad
            ],
        }

    def oldest_json(self) -> dict[str, object]:
        """List the oldest open cards, as nemik-history --oldest prints them (nemik:W853).

        The same oldest_rows the command calls, over the queue files under the export root. It
        reads files and spawns nothing.

        Returns:
            {"oldest": the rows}: cite, age_days, status, flag, blocked_on, title, path, offline and
            reach for each of the OLDEST_SHOWN oldest open cards, oldest first.

        """
        files = dict(workstream_files(self.root, QUEUE))
        return {"oldest": oldest_rows(files, self.root, OLDEST_SHOWN)}

    def collapse_json(self) -> dict[str, object]:
        """List the collapse umbrellas and the enables edges that escape them (nemik:W864).

        The lines nemik-collapse prints, over the graph less what luthen withholds. It reads the
        graph the server already holds and starts no process.

        Returns:
            {"lines": the umbrella lines, one string each}.

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        return {"lines": collapse_lines(blocked_rows(g))}

    def umbrellas_json(self) -> dict[str, object]:
        """List the collapse umbrellas with their members' n-path addresses (nemik:W973).

        Returns:
            {"umbrellas": the rows umbrella_docs gives}, over the graph less what luthen withholds.

        """
        g = without(self.graph, self.withheld) if self.withheld else self.graph
        return {"umbrellas": umbrella_docs(g)}

    def doc_for(self, route: str) -> dict[str, object]:
        """Build the document a route in DOC_ROUTES answers.

        Returns:
            The document the route names.

        """
        docs: dict[str, Callable[[], dict[str, object]]] = {
            "/hostroot.json": self.hostroot_doc,
            "/oldest.json": self.oldest_json,
            "/collapse.json": self.collapse_json,
            "/series.json": self.series_doc,
            "/check.json": self.check_doc,
            "/landings.json": self.landings_doc,
            "/critical.json": self.critical_json,
            "/starved.json": self.starved_json,
            "/queue.json": self.queue_json,
            "/overlaps.json": self.overlaps_json,
            "/pacing.json": self.pacing_json,
            "/floor-asks.json": self.floor_asks_json,
        }
        return docs[route]()

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
        """Render the model's own gauges in the Prometheus text format.

        Returns:
            The build version, graph size, rebuild count and the CPU seconds of the last rebuild
            and of each of its phases.

        """
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


def local(term: object) -> str:
    """Give the last segment of a nemik:/oslc IRI: after '#', '/', or the urn:nemik: prefix.

    Returns:
        The term's last segment, after any urn:nemik: prefix, '#' or '/'.

    """
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


def umbrella_docs(g: Graph) -> list[dict[str, object]]:
    """List the collapse umbrellas over a graph, as a document of their own (nemik:W973).

    An umbrella is a view over blocked cards, never a card (nemik:W691), so it is not a node in
    graph.json: it is its own document. Pass the graph without the withheld cards.

    Returns:
        One row per member of each umbrella: the umbrella's id, blockers and enables, and the
        member card with its n-path address.

    """
    blocked = blocked_rows(g)
    found = collapse(blocked)
    address = paths(blocked, found)
    return [
        {
            "id": name,
            "blockers": blockers,
            "enables": enables,
            "card": m,
            "address": address[m],
        }
        for name, blockers, enables, members in found
        for m in members
    ]


def without(g: Graph, refs: frozenset[str]) -> Graph:
    """nemik:W309: a copy of `g` without every withheld waypoint and every edge to or from it.

    It is the graph the public numbers are computed over.

    Returns:
        A new graph holding every triple that touches no withheld waypoint.

    """
    from nemik.withheld import _id

    out = Graph()
    gone = {URIRef(_id(r)) for r in refs}
    for s, p, o in g:
        if s not in gone and o not in gone:
            out.add((s, p, o))
    return out


def to_json(g: Graph, findings: dict, numbers: Graph | None = None) -> dict:
    """Build the view's document.

    nemik:W403: built with identical flow solves answered once (the ranking, edge widths and
    operator-ask weights each asked for the same repo's solve). nemik:W412: and with each graph's
    per-card facts indexed once.

    Returns:
        The view's document, as _to_json builds it inside the memo and index scopes.

    """
    from nemik.index import indexed
    from nemik.salience import memo_audits

    with memo_audits(), indexed():
        return _to_json(g, findings, numbers)


def stage_of(g: Graph, n: URIRef) -> str:
    """Say which stage a card is in beyond its status (nemik:W767).

    Returns:
        "gating" while a queued or gating commit stack names the card (nemik:inGate), else "".

    """
    return "gating" if g.value(n, NEMIK.inGate) is not None else ""


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
                    # nemik:W740: the clocks a reader may order the card list by
                    "last_worked": str(g.value(n, NEMIK.lastWorked) or ""),
                    "issued": str(g.value(n, DCTERMS.created) or ""),
                    "stage": stage_of(g, URIRef(str(n))),
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
    # One (blocked, blocker) pair can have several inbound rows (linux-sources:W40 waits on the
    # mtools session AND mtools:W24 AND mtools:W46). Keeping only the last row made which claims got
    # drawn depend on hash order (nemik:W119), so the claims are merged.
    by_blocked: dict[tuple[str, str], dict] = {}
    for blk in blocks:
        fresh = dict(blk)
        fresh["claimed_by"] = []
        m = by_blocked.setdefault((blk["blocked"], blk["blocker"]), fresh)
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

    # nemik:W460: an errand is the operator's own business: nemik-operator lists it, the view does
    # not.
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
    # the page can mark the path that bounds the fleet. Computed over `gn` like every published
    # number.
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
    # as waiting: its fill says ready, but the flow model counts it as waiting and gives it no
    # salience. nemik:W684: a ready leaf with no manifest cannot be stacked, so it is drawn waiting
    # for one. nemik:W687: and a card that throws a Warning on the CLI carries it, for the badge.
    from nemik.blocks import node_flags

    marks = node_flags(g, findings)
    for item in nodes:
        item.update(marks.get(item["id"], {}))
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
    nodes.sort(key=operator.itemgetter("id"))
    for item in nodes:
        item["blocked_on"] = sorted(item["blocked_on"])
    edges.sort(key=operator.itemgetter("source", "target", "kind"))
    # nemik:W317: each repo's red/amber/green from the declared thresholds, over `gn` like every
    # number.
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


def ruler_table(edges: list[dict], asks: list[AskRow]) -> dict[str, list[str]]:
    """nemik:W418: the ruler-sequence patterns the page draws, from mtools' generator (mtools:W1048).

    `motif[k]` is the order-k motif (one per halo scope, orders 0..3). `f[n]` is F(n), the pattern
    of the n-th line into one blocker; which lines a view shows is the page's choice, so it indexes
    this table rather than the server fixing each line's n. A line's n is at most the lines into its
    blocker or into an ask chip (one per category and repo), so the table runs to the larger of
    those.

    Returns:
        The patterns: `motif` (orders 0 to 3) and `f` (F(n) for n up to the larger
        line count).

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


HISTORY_PREFIX = "/history/"
SECONDS_PER_HOUR = 3600


def history_response(
    directory: Path | None, path: str, now: datetime
) -> tuple[int, str, bytes]:
    """Answer /history/<mode>.json from the document nemik-history --publish wrote (nemik:W854).

    The modes that read git cannot run here (the server never spawns), so the host runs them and
    publishes each result; this reads the file back and says how old it is. Only the modes named
    in histdocs.MODES have a file, so a path never reaches another one.

    Args:
        directory: The --history-dir, or None when the server was not given one.
        path: The request path.
        now: The time freshness is judged at.

    Returns:
        (status, content type, body): (200, JSON, the wrapped document) or (404, text, a
        reason); no board is ever guessed.

    """
    if directory is None:
        return 404, "text/plain", b"no --history-dir"
    mode = path.removeprefix(HISTORY_PREFIX).removesuffix(".json")
    name = file_name(mode)
    if not name:
        return 404, "text/plain", b"not a history document"
    try:
        text = (directory / name).read_text(encoding="utf-8")
    except OSError:
        return 404, "text/plain", b"no document published"
    as_of, body = decode(text)
    cutoff = datetime.fromtimestamp(
        now.timestamp() - STALE_HOURS * SECONDS_PER_HOUR, UTC
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    wrapped = wrap(mode, as_of, body, cutoff)
    if not wrapped:
        return 404, "text/plain", b"unreadable document"
    return 200, "application/json", wrapped.encode("utf-8")


def handler(model: Model) -> type[BaseHTTPRequestHandler]:
    """Build the live server's request handler class over one model.

    The page and the vendor directory are read once here; each GET pokes the model (except a
    metrics scrape) and answers from its cached graph and documents.

    Args:
        model: the model every request reads, and pokes to refresh.

    Returns:
        The handler class, for ThreadingHTTPServer to instantiate per request.

    """
    page = files("nemik.web").joinpath("index.html").read_bytes()
    vendor = files("nemik.web").joinpath("vendor")

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self.send(200, "text/html; charset=utf-8", page)
                return
            if (own := page_file(self.path.lstrip("/"))) is not None:
                self.send(200, PAGE_FILES[self.path.lstrip("/")], own)
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
            if self.path in {"/wake", "/wake.json"}:
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
            elif self.path in {"/operator", "/operator.json"}:
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
            elif self.path.startswith("/check/"):
                answer = model.check_reply(self.path)
                self.send(answer[0], answer[1], answer[2])
            elif self.path in DOC_ROUTES:
                host_body = json.dumps(model.doc_for(self.path), indent=1).encode()
                self.send(200, "application/json", host_body)
            elif self.path.startswith(HISTORY_PREFIX):
                self.send(
                    *history_response(model.history_dir, self.path, datetime.now(UTC))
                )
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
    """nemik:W169: the page and its scripts as files under `out`, every link relative.

    So the view works from any bucket subpath. Data files are W170's, the gate is W172's.

    Returns:
        The files written: index.html, the vendor files and the page's own files that
        exist.

    """
    web = files("nemik.web")
    written = [out / "index.html"]
    (out / "vendor").mkdir(parents=True, exist_ok=True)
    page = web.joinpath("index.html").read_text()
    # nemik:W397: the page no longer has a Tools panel (W171 cut it here), so it is written as it
    # is.
    written[0].write_text(page)
    for name in sorted(VENDOR):
        dst = out / "vendor" / name
        dst.write_bytes(web.joinpath("vendor").joinpath(name).read_bytes())
        written.append(dst)
    for name in sorted(PAGE_FILES):  # nemik:W801: the page's own files that exist yet
        body = page_file(name)
        if body is not None:
            (out / name).write_bytes(body)
            written.append(out / name)
    return written


def static_data(model: Model) -> dict[str, object]:
    """nemik:W170: every document the page fetches, computed once from one export.

    Shaped as {published path: document}. Only what the page reads is published:
    inbound/<repo>.json was planned, but the page never fetches it, so it stays off the public
    surface.

    Returns:
        The documents by published path: graph, wake, goals per repo, history and
        umbrellas.

    """
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
    open_g = without(g, model.withheld) if model.withheld else g
    docs["umbrellas.json"] = umbrella_docs(open_g)
    return docs


def history_doc(
    root: Path, withheld: frozenset[str] = frozenset()
) -> dict[str, list[dict[str, Any]]]:
    """nemik:W308: the project-manager's weekly roll-up per repo, from each repo's committed queue.

    Counts and days only: the roll-up row's `oldest_blocked` symbol is dropped, so nothing here
    names a waypoint, and a withheld waypoint (nemik:W309) is left out of every snapshot before
    counting. It needs git history, so only a host-side build has it (the pod has none).

    Returns:
        Per repo, the weekly roll-up rows without the `oldest_blocked` field.

    """
    from nemik.history import snapshots, weekly

    out: dict[str, list[dict[str, Any]]] = {}
    for repo, path in workstream_files(root, QUEUE):
        hide = {r.partition(":")[2] for r in withheld if r.partition(":")[0] == repo}
        snaps = []
        for at, q in snapshots(path.parents[1]):
            kept = dict(q)
            kept["waypoints"] = [
                w for w in q.get("waypoints", []) if w["symbol"] not in hide
            ]
            snaps.append((at, kept))
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
    """nemik:W153 (see _build_static), inside the live server's per-build scope (nemik:W412, W403).

    The scope is the one the live server's document is built in: each graph indexed once and each
    flow solve answered once. The build ran outside it, so the goals, the pieces and the TRS feeds
    asked rdflib 1.09 M times for facts the index holds (a warm publish profiled at 94 s, a third
    of it in rank.goals).

    Returns:
        The files written, as _build_static returns them.

    """
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
    """nemik:W153: the gated static view under `out`.

    Every check runs before anything is written, so a refused build leaves `out` untouched; the
    withheld list itself is never copied into it.

    nemik:W503: `private` is the pod's own build: nothing is withheld unless a list is given, and
    the files the live server answered beyond the public view are written too (see private_files).

    nemik:W634: with `exports`, each repo's own export (docs/withholding-at-source.md) also decides
    what leaves it, failing closed per repo: a repo with no export publishes none of its cards.

    Returns:
        The files written under `out`: the page, the data documents, the feeds and
        hashes.json, and the private files when `private`.

    """
    from nemik.apischema import unmanifested
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
    # nemik:W440: the contract the published files keep, generated from the field manifest and
    # listed in hashes.json like the data, so a client sees when it changes
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
        bodies[f"outbox/{repo}.jsonld"] = outbox(
            repo, model.graph, hidden, root / LOG_FILE
        )
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


def ready_cards(nodes: list[dict[str, object]]) -> dict[str, int]:
    """Count the cards in state ready by repo, for the round gauges (nemik:W1082).

    Args:
        nodes: The graph document's nodes, each with a repo and a state.

    Returns:
        {repo: how many of its cards are ready}; a node with no repo is skipped.

    """
    out: dict[str, int] = {}
    for node in nodes:
        repo = node.get("repo")
        if node.get("state") == "ready" and isinstance(repo, str):
            out[repo] = out.get(repo, 0) + 1
    return out


def round_bindings(
    graph: Graph, nodes: list[dict[str, object]], landings: Path
) -> dict[str, str]:
    """Name the term that bounded each repo's round, for the round gauges (nemik:W1167).

    Args:
        graph: The merged queue graph, which holds each card's planned files.
        nodes: The graph document's nodes, each with a repo, a symbol and a state.
        landings: The landing file the round's stack sizes are read from.

    Returns:
        {repo: its binding term} by roundcli.size_for over the repo's ready and working cards, as
        nemik-rank --round reads them; a repo with none is absent.

    """
    by_repo: dict[str, list[dict[str, object]]] = {}
    for node in nodes:
        repo, symbol, state = node.get("repo"), node.get("symbol"), node.get("state")
        if (
            state in {"ready", "working"}
            and isinstance(repo, str)
            and isinstance(symbol, str)
        ):
            by_repo.setdefault(repo, []).append(
                {"state": state, "manifest": manifest(graph, repo, symbol)}
            )
    return bindings_of(by_repo, landings)


def working_cards(nodes: list[dict[str, object]]) -> dict[str, list[str]]:
    """Group the cards being worked by repo, for the round gauges (nemik:W1025).

    Args:
        nodes: The graph document's nodes, each with a repo, a symbol, a state and a stage.

    Returns:
        {repo: the symbols of its cards whose state is working or that a queued or gating commit
        stack names (stage gating, nemik:W1062)}; a node without a repo and symbol is skipped.

    """
    out: dict[str, list[str]] = {}
    for node in nodes:
        repo, symbol = node.get("repo"), node.get("symbol")
        if (
            (node.get("state") == "working" or node.get("stage") == "gating")
            and isinstance(repo, str)
            and isinstance(symbol, str)
        ):
            out.setdefault(repo, []).append(symbol)
    return out


def cost_gauges() -> list[str]:
    """Write what this build has cost so far as gauges (nemik:W1064, W1074).

    The builder is a fresh process on every pass, so its peak is the cost of one build and the
    series shows whether it grows. Under a memory limit the resident peak saturates at the limit,
    the excess going to swap, so the process's swap and the container's own peak and swap peak sit
    beside it, and the pod and whether the build started from a restored cache label every sample.

    Returns:
        The gauge lines, Prometheus text.

    """
    status = Path("/proc/self/status")
    status_text = status.read_text(encoding="utf-8") if status.is_file() else ""
    peak_file = Path("/sys/fs/cgroup/memory.peak")
    swap_file = Path("/sys/fs/cgroup/memory.swap.peak")
    peaks = (
        bytes_of(peak_file.read_text(encoding="utf-8") if peak_file.is_file() else ""),
        bytes_of(swap_file.read_text(encoding="utf-8") if swap_file.is_file() else ""),
    )
    warm = int(os.environ.get("NEMIK_CACHE_HIT", "0") == "1")
    return build_cost_lines(
        peak_kib_of(status_text),
        swap_kib_of(status_text),
        peaks,
        int(time.process_time() * 1000),
        labels_of(os.environ.get("NEMIK_POD", ""), warm),
    )


def private_files(model: Model, out: Path) -> list[Path]:
    """nemik:W503: what the live server answered beyond the public view, as files.

    They are /operator.json, /inbound.json and /inbound/<repo>.json (one per repo, empty when
    nothing waits on it), /graph.ttl, /metrics with the snapshot's own age gauge, and the source
    key the next publish compares. Never part of the public build: these name every waypoint's
    asks and blockers.

    Returns:
        The files written under `out`.

    """
    made: list[Path] = []

    def put(name: str, body: bytes) -> None:
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(body)
        made.append(dst)

    def dump(doc: object) -> bytes:
        return json.dumps(doc, indent=1).encode()

    rows = model.doc["inbound"]
    nodes: list[dict[str, object]] = model.doc["nodes"]
    put("operator.json", dump(model.doc["operator"]))
    # nemik:W978: the landings board, as /landings.json answers it live, from the file in the root
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    put("landings.json", dump(landings_board(model.root / LANDINGS_FILE, now)))
    put("inbound.json", dump(rows))
    repos = {str(n["repo"]) for n in nodes if n["repo"]}
    for repo in sorted(repos | {str(b["blocker"]) for b in rows}):
        put(f"inbound/{repo}.json", dump([b for b in rows if b["blocker"] == repo]))
    # N-Triples, which is Turtle with one triple per line: the same RDF a /graph.ttl reader parses,
    # without the grouping and sorting that made the Turtle serializer the costliest single write of
    # the build
    put("graph.ttl", model.graph.serialize(format="nt").encode())
    gauge = (
        "# TYPE nemik_snapshot_published_seconds gauge\n"
        f"nemik_snapshot_published_seconds {time.time():.0f}\n"
    )
    # nemik:W990: the ratchet pace board and its gauges, from the pace run's file in the root
    pace, pace_lines = pace_board(model.root / PACE_FILE)
    put("ratchet-pace.json", dump(pace))
    # nemik:W1025: the round gauges, from the published round file and the cards being worked; a
    # missing or refused file publishes nemik_round_readable at 0, never nothing
    round_path = model.root / ROUND_FILE
    round_text = round_path.read_text(encoding="utf-8") if round_path.is_file() else ""
    round_lines = round_board(
        round_text,
        working_cards(nodes),
        ready_cards(nodes),
        round_bindings(model.graph, nodes, model.root / LANDINGS_FILE),
    )
    cost_lines = cost_gauges()
    # nemik:W1138: one series per open card, the record un-flattened, aggregated at query time
    cards = [{k: v for k, v in n.items() if isinstance(v, str)} for n in nodes]
    put(
        "metrics",
        model.metrics()
        + gauge.encode()
        + "\n".join(
            [*pace_lines, *round_lines, *cost_lines, *card_lines(cards), ""]
        ).encode(),
    )
    return made


def fleet_key(root: Path) -> str:
    """Give the digest of every queue and ledger file's path and CONTENT now.

    Content, not mtime: an export that rewrites a file without changing it (luthen's does, every
    minute) is not a change, and a build costs real CPU (luthen-observability, nemik:W504: the
    builder rebuilds on a changed content hash).

    Returns:
        The sha256 hex digest.

    """
    import hashlib

    digest = hashlib.sha256()
    for name in (QUEUE, LEDGER):
        for _, path in workstream_files(root, name):
            digest.update(str(path).encode() + b"\0" + path.read_bytes() + b"\0")
    # nemik:W949: a changed log file rebuilds the outboxes that carry it
    if (root / LOG_FILE).is_file():
        digest.update(b"log\0" + (root / LOG_FILE).read_bytes() + b"\0")
    # nemik:W978: and a changed landings file rebuilds the board baked into the private files
    if (root / LANDINGS_FILE).is_file():
        digest.update(b"landings\0" + (root / LANDINGS_FILE).read_bytes() + b"\0")
    # nemik:W990: and a changed pace file rebuilds the board and the gauges
    if (root / PACE_FILE).is_file():
        digest.update(b"pace\0" + (root / PACE_FILE).read_bytes() + b"\0")
    # nemik:W1025: and a changed round file rebuilds the round gauges
    if (root / ROUND_FILE).is_file():
        digest.update(b"round\0" + (root / ROUND_FILE).read_bytes() + b"\0")
    return digest.hexdigest()


def publish(
    root: Path,
    base: Path,
    withheld: Path | None,
    keep: int = 3,
    exports: Path | None = None,
) -> Path | None:
    """nemik:W503: build a private snapshot under base/snap-<stamp>-<pid>/ and flip current to it.

    The flip is one atomic rename. The build runs in this short-lived process, so every byte of
    its graph is returned to the OS when it exits (nemik:W500: rebuilding in a long-lived process
    left ~20 MB of fragmented heap per build). Returns None when no queue or ledger changed since
    current/ was built. The last `keep` snapshots stay, so a request already reading one is not
    pulled out from under it.

    Returns:
        The new snapshot's path, or None when no queue or ledger changed since
        current/ was built.

    """
    from nemik import adapter, cachestore, lastgood

    # nemik:W1096: this process builds once and exits, so the parse cache only doubles the graphs
    adapter.forget_parsed()
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
    # nemik:W1086: a pod with no snapshot of its own serves the last good one kept on the claim
    # while it builds, so a build the memory limit kills no longer leaves the Service endpointless
    lastgood.restore(base, base / ".cache")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    snap = base / f"snap-{stamp}-{os.getpid()}"
    # nemik:W518: start warm, as the long-lived server was; W1074: and say so on the build's gauges
    restored = cachestore.load(base / ".cache")
    os.environ["NEMIK_CACHE_HIT"] = "1" if restored else "0"
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
    Path(link).replace(base / "current")
    for old in sorted(p for p in base.glob("snap-*") if p.is_dir())[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    # nemik:W1086: the next pod serves this at once; a full claim must not fail a good build
    try:
        lastgood.save(snap, base / ".cache")
    except OSError as e:
        sys.stderr.write(f"last-good not kept: {e}\n")
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
    hostroot: Path | None
    landings: Path | None
    history_dir: Path | None
    exports: Path | None
    publish: Path | None


def main(argv: list[str] | None = None) -> None:
    """Run nemik-serve: publish a snapshot, write the static view, or serve the live one.

    With --publish it builds a private snapshot and exits, printing its path or "unchanged".
    With --static it writes the view as files and exits. Otherwise it serves the live model and
    prints the bound port once the socket listens. A stale withheld list, or a build error,
    exits 2 with the cause on stderr.

    Args:
        argv: the command line, or None for sys.argv.

    Raises:
        SystemExit: with 2 when the withheld list is stale or a build fails.

    """
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
        "--hostroot",
        type=Path,
        metavar="FILE",
        help="the live server only: the host-root frontier nemik-hostroot writes on the host "
        "(host-root.json), served as /hostroot.json with each row's staleness; a missing or "
        "unreadable file serves no board, and the static view never carries it (nemik:W780)",
    )
    ap.add_argument(
        "--landings",
        type=Path,
        metavar="FILE",
        help="the live server only: the commit landings nemik-hostroot --landings writes on the "
        "host (landings.json), served as /landings.json with its staleness; a missing or "
        "unreadable file serves no board (nemik:W751)",
    )
    ap.add_argument(
        "--history-dir",
        type=Path,
        metavar="DIR",
        help="the live server only: the history documents nemik-history --publish writes on the "
        "host, served as /history/<mode>.json with their age; a missing file serves not-found "
        "(nemik:W854)",
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
        print(snap or "unchanged")
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
    model.hostroot = args.hostroot
    model.landings = args.landings
    model.history_dir = args.history_dir
    server = ThreadingHTTPServer((args.bind, args.port), handler(model))
    # nemik:W1060: the bound port is told once the socket listens, so a caller that passed --port 0
    # learns it from this process and never from a number it picked, closed and hoped to keep.
    sys.stdout.write(f"listening {server.server_address[1]}\n")
    sys.stdout.flush()
    server.serve_forever()


if __name__ == "__main__":
    main()
