# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-wake: which blocked-on entities must be awake, and which are not.

Joins what is waiting on each workstream (nemik.blocks.inbound: other repos' open waypoints
blocked on it) with whether that workstream has a live session, read from luthen's
`loop_liveness` JSON. nemik does not detect liveness itself.

Awake states, from loop_liveness's verdict:
    asleep     no live session (verdict "dormant"): wake it
    idle       a live session whose loop is not ticking (stale / disarmed / unknown / future)
    awake      a live session ticking ("ok")
    unknown    no liveness reading for this repo

Liveness source, first found: --liveness FILE ('-' for stdin); <root>/liveness.json (the export
luthen writes for the pod); luthen-observability's own `python -m checks.loop_liveness`, run
through its venv, when that tree exists beside the root.
"""

from __future__ import annotations

import argparse
import json
import operator
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from mikemol.hooks import rewake
from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.adapter import BASE, NEMIK
from nemik.blocks import inbound, operator_asks
from nemik.luthenseries import load
from nemik.pacecli import EXPORT_TREE

if TYPE_CHECKING:
    from rdflib.term import Node

    from nemik.luthenseries import Series

# nemik:W549: mtools' mikemol.hooks.rewake (mtools:W1299) owns the constant and the pure pair.
REWAKE_S = rewake.REWAKE_S

AWAKE = {"ok": "awake", "dormant": "asleep"}


class LivenessRecord(TypedDict, total=False):
    """One repo's loop liveness as luthen's checks.loop_liveness writes it."""

    verdict: str
    last_tick: str
    history: list[list[str]]


Liveness = dict[str, LivenessRecord]


class Alarm(TypedDict, total=False):
    """One fired alarm as fired_alarms builds it; an error row has no message."""

    ref: str
    repo: str
    trigger: str
    error: str
    state: str
    at: str
    recurrence_id: str
    title: str
    message: str


class Waiter(TypedDict, total=False):
    """One thing a roster row waits on; only the operator's carry a salience."""

    blocked: str
    claimed_by: list[str]
    title: str
    salience: float


class WakeRow(TypedDict, total=False):
    """One roster row: a workstream, its liveness, and what waits on it."""

    repo: str
    state: str
    last_tick: str
    last_tick_age_s: float | None
    waiting: list[Waiter]


def read_liveness(root: Path, source: str | None) -> tuple[Liveness, str]:
    """Return ({repo: record}, where it came from); ({}, reason) when there is none.

    Returns:
        The liveness record by repo, and where it came from; empty and the reason when
        there is none.

    """
    document: dict[str, Liveness]
    try:
        if source == "-":
            document = json.load(sys.stdin)
            return document["repos"], "stdin"
        if source:
            document = json.loads(Path(source).read_text(encoding="utf-8"))
            return document["repos"], source
        export = root / "liveness.json"
        if export.exists():
            document = json.loads(export.read_text())
            return document["repos"], str(export)
        luthen = root / "luthen-observability"
        py = luthen / ".venv" / "bin" / "python"
        if py.exists():
            out = subprocess.run(
                [str(py), "-m", "checks.loop_liveness"],
                cwd=luthen,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            document = json.loads(out)
            return document["repos"], "luthen-observability checks.loop_liveness"
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        return {}, f"unreadable: {exc}"
    return {}, "no liveness source"


def age_seconds(last_tick: str | None, now: datetime | None = None) -> float | None:
    """Seconds between an ISO-8601 `last_tick` and `now` (default: real now); None if unusable.

    A caller gets an age, not a raw timestamp it has to subtract itself -- the gap luthen's W117
    named (nemik:W18).

    Returns:
        The age in seconds, or None when the stamp is unusable.

    """
    return rewake.age_seconds(last_tick, now or datetime.now(UTC))


def should_nudge(
    last_nudged: float | None, now: datetime | None = None, rewake_s: int = REWAKE_S
) -> bool:
    """Say whether to nudge again, given when (unix seconds, or None) it was last nudged.

    nemik:W18/luthen W117: the backoff+dedup decision luthen's checks/waker.py currently
    reinvents per-repo (a REWAKE_S threshold plus a seen-timestamp file). This is that decision,
    factored out as a pure function -- it takes no side effect and owns no state file itself;
    the caller decides WHICH rows are nudge candidates (e.g. state in asleep/idle, or
    stale/future/unknown) and where `last_nudged` came from and gets recorded.

    Returns:
        True when the backoff has elapsed or the repo was never nudged.

    """
    return rewake.should_nudge(last_nudged, now or datetime.now(UTC), rewake_s)


def roster(
    g: Graph,
    liveness: Liveness,
    *,
    now: datetime | None = None,
    alarms: list[Alarm] | None = None,
) -> list[WakeRow]:
    """One row per workstream something is waiting on, sleepers with waiters first.

    nemik:W151: a fired alarm (fired_alarms) whose owner is not awake also puts the owner on the
    roster, waiting on itself, so the same wake/nudge path that wakes a blocker wakes it. An awake
    owner gets W168's send-ready line instead and no row.

    Returns:
        The roster rows, sleepers with waiters first.

    """
    rows: dict[str, WakeRow] = {}
    for a in alarms or []:
        if (
            a.get("error")
            or a["state"] == "awake"
            or (a.get("message") and a["state"] == "idle")
        ):
            continue
        rec = liveness.get(a["repo"])
        last_tick = (rec or {}).get("last_tick") or ""
        row = rows.setdefault(
            a["repo"],
            {
                "repo": a["repo"],
                "state": a["state"],
                "last_tick": last_tick,
                "last_tick_age_s": age_seconds(last_tick, now),
                "waiting": [],
            },
        )
        row["waiting"].append(
            {
                "blocked": a["ref"],
                "claimed_by": [a["ref"]],
                "title": f"alarm fired {a['at']}: {a['title']}",
            }
        )
    for b in inbound(g):
        rec = liveness.get(b["blocker"])
        last_tick = (rec or {}).get("last_tick") or ""
        row = rows.setdefault(
            b["blocker"],
            {
                "repo": b["blocker"],
                "state": "unknown"
                if rec is None
                else AWAKE.get(rec.get("verdict", ""), "idle"),
                "last_tick": last_tick,
                "last_tick_age_s": age_seconds(last_tick, now),
                "waiting": [],
            },
        )
        row["waiting"].append(
            {
                "blocked": b["blocked"],
                "claimed_by": b["claimed_by"],
                "title": b["title"],
            }
        )
    order = {"asleep": 0, "idle": 1, "unknown": 2, "awake": 3}
    return sorted(
        rows.values(), key=lambda r: (order[r["state"]], -len(r["waiting"]), r["repo"])
    )


def fired_alarms(
    g: Graph, start: datetime, end: datetime, liveness: Liveness
) -> list[Alarm]:
    """Every alarm that fired in [start, end) on an open waypoint, oldest first (nemik:W149).

    Alarms live on waypoints (mtools:W279), with their anchors (W300) and recurrence (W309/W310);
    nemik.alarm resolves each to its instants. The owner's liveness says who can act on it now.

    Returns:
        The fired alarms, oldest first; a bad alarm is an error row.

    """
    from nemik.adapter import BASE, NEMIK, OSLC_CM
    from nemik.alarm import fires_between

    def val(n: Node, p: Node) -> str:
        return str(g.value(n, p) or "")

    out: list[Alarm] = []
    for n in sorted(set(g.subjects(NEMIK.alarm, None)), key=str):
        if (n, OSLC_CM.state, NEMIK.Done) in g:
            continue
        repo, _, sym = str(n).removeprefix(BASE).partition("/")
        rec = liveness.get(repo)
        state = "unknown" if rec is None else AWAKE.get(rec.get("verdict", ""), "idle")
        for trig in sorted(str(t) for t in g.objects(n, NEMIK.alarm)):
            try:
                hits = fires_between(
                    trig,
                    start,
                    end,
                    dtstart=val(n, NEMIK.dtstart),
                    due=val(n, NEMIK.due),
                    rrule=val(n, NEMIK.rrule),
                    exdates=tuple(sorted(str(x) for x in g.objects(n, NEMIK.exdate))),
                    done={str(r): "" for r in g.objects(n, NEMIK.occurrenceDone)},
                )
            # One bad alarm (a hand-edited queue) must not hide the rest. What a bad one raises: the
            # RFC 5545 and RRULE parsers' ValueError, a naive-versus-aware TypeError, a year out of
            # range.
            except (ValueError, TypeError, OverflowError) as e:
                out.append(
                    {
                        "ref": f"{repo}:{sym}",
                        "repo": repo,
                        "trigger": trig,
                        "error": str(e),
                        "state": state,
                        "at": "",
                        "recurrence_id": "",
                        "title": val(n, DCTERMS.title),
                    }
                )
                continue
            out += [
                {
                    "ref": f"{repo}:{sym}",
                    "repo": repo,
                    "trigger": trig,
                    "at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "recurrence_id": rid,
                    "state": state,
                    "title": val(n, DCTERMS.title),
                }
                for at, rid in hits
            ]
    # nemik:W168: an owner with a live session (awake or idle) gets a line ready to send as is: the
    # first line stands alone (the recipient previews only it) and cites the waypoint. An asleep or
    # unknown owner gets none; waking it is the roster's job (nemik:W151).
    for a in out:
        if a["state"] in {"awake", "idle"} and not a.get("error"):
            occ = f" (occurrence {a['recurrence_id']})" if a["recurrence_id"] else ""
            a["message"] = (
                f"nemik → {a['repo']}: alarm on {a['ref']} fired at {a['at']}{occ}: {a['title']}\n"
                f"Trigger {a['trigger']}, as stored on the waypoint. Act on it, or move the alarm."
            )
    return sorted(out, key=operator.itemgetter("at", "ref", "trigger"))


def operator_row(g: Graph) -> WakeRow:
    """Return the operator as a roster row: every needs-you ask waiting, heaviest first.

    Args:
        g: the graph the asks are read from.

    Returns:
        A roster row with repo "operator" and state "you", whose waiting entries carry each ask's
        ref, title and salience.

    """
    from nemik.blocks import with_salience

    # nemik:W298: heaviest first, each with the demand waiting behind it.
    needs = [
        a for a in with_salience(g, operator_asks(g)) if a["category"] == "needs-you"
    ]
    return {
        "repo": "operator",
        "state": "you",
        "last_tick": "",
        "waiting": [
            {
                "blocked": a["ref"],
                "claimed_by": [],
                "title": a["ask"],
                "salience": a["salience"],
            }
            for a in needs
        ],
    }


def nudges_path() -> Path:
    """Locate the nudge state file: nemik/nudges.json under XDG_STATE_HOME, or ~/.local/state.

    Returns:
        The path of nudges.json.

    """
    import os

    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(state) / "nemik" / "nudges.json"


def due_nudges(
    rows: list[WakeRow], seen: dict[str, float], now: datetime | None = None
) -> list[WakeRow]:
    """Rows worth nudging now (asleep or idle, something waiting, backoff not active).

    `seen` is {repo: unix_seconds_last_nudged}, read and written by the caller (nudges_path() by
    default) -- should_nudge() itself owns no state file. Mutates `seen` in place for the repos
    returned, so a caller can write it straight back out.

    Returns:
        The rows to nudge, with `seen` updated for them.

    """
    now = now or datetime.now(UTC)
    due = []
    for r in rows:
        if r["state"] not in {"asleep", "idle"} or not r["waiting"]:
            continue
        if not should_nudge(seen.get(r["repo"]), now):
            continue
        seen[r["repo"]] = now.timestamp()
        due.append(r)
    return due


def _read_seen(path: Path) -> dict[str, float]:
    try:
        seen: dict[str, float] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return seen


def _write_seen(path: Path, seen: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, sort_keys=True), encoding="utf-8")


def alarm_key(a: Alarm) -> str:
    """nemik:W166: a firing's identity, (ref, RECURRENCE-ID, instant), in the nudges state's keys.

    Repo names (the state's other keys) never contain '|', so the two cannot collide.

    Returns:
        The key, `alarm|<ref>|<recurrence id>|<instant>`.

    """
    return f"alarm|{a['ref']}|{a['recurrence_id']}|{a['at']}"


def undelivered(
    fired: list[Alarm], seen: dict[str, float], now: datetime | None = None
) -> list[Alarm]:
    """Pick undelivered fired alarms, marking each delivered in `seen` (mutated, like due_nudges).

    A firing is delivered once: the same (ref, occurrence, instant) seen again by an overlapping
    window is skipped. Error rows (a bad trigger) have no instant, are never marked, and so stay
    visible every run until the queue is fixed.

    Returns:
        The alarms not yet delivered, error rows included.

    """
    now = now or datetime.now(UTC)
    out: list[Alarm] = []
    for a in fired:
        if a.get("error"):
            out.append(a)
            continue
        k = alarm_key(a)
        if k in seen:
            continue
        seen[k] = now.timestamp()
        out.append(a)
    return out


def series_lines(
    series: Series, repos: list[str], *, only: bool = False
) -> list[str]:
    """One '<repo> <verdict> <as_of>' line per repo, from luthen's series snapshot (nemik:W1281).

    A repo the series has no entry for, or an entry with no verdict, reads 'no sample': never ok or
    dormant, which would state a liveness nobody measured. Every line carries the snapshot's as_of,
    so a reader can judge whether the reading postdates the event it classifies.

    Args:
        series: The snapshot, already refused if it was stale.
        repos: The repos to report, joined with the series' own.
        only: Report exactly `repos`, and none of the series' others (nemik:W1287).

    Returns:
        The lines, sorted by repo.

    """
    as_of = datetime.fromtimestamp(series.as_of, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[str] = []
    names = set(repos) if only else set(repos) | set(series.repos)
    for repo in sorted(names):
        entry = series.repos.get(repo)
        verdict = entry.verdict if entry is not None and entry.verdict else "no sample"
        out.append(f"{repo} {verdict} {as_of}")
    return out


def workstreams(g: Graph) -> list[str]:
    """Name the repos whose workstreams the graph holds.

    Returns:
        The repo names, sorted.

    """
    return sorted(
        {
            str(n).removeprefix(BASE).partition("/")[0]
            for n in g.subjects(NEMIK.workstream, None)
        }
    )


def series_report(
    repos: list[str], series_file: Path, max_age: int, *, only: bool = False
) -> None:
    """Print the series lines, or refuse when the snapshot cannot be trusted (nemik:W1281).

    Args:
        repos: Repos to report beside the series' own; one the series lacks reads 'no sample'.
        series_file: luthen-series.json.
        max_age: The oldest as_of accepted, in seconds.
        only: Print exactly `repos`; with none named there is nothing to print (nemik:W1287).

    Raises:
        SystemExit: The file is missing, unreadable, unversioned, malformed or too old, or --only
            names no repo; the reason is on stderr and nothing is on stdout.

    """
    if only and not repos:
        sys.stderr.write("series: --only needs at least one --repo\n")
        raise SystemExit(1)
    now = int(datetime.now(UTC).timestamp())
    try:
        series = load(series_file, now, max_age)
    except (OSError, ValueError, TypeError) as exc:
        sys.stderr.write(f"series: {exc}\n")
        raise SystemExit(1) from exc
    sys.stdout.write("\n".join(series_lines(series, repos, only=only)) + "\n")


def series_path(args: Options) -> Path:
    """Locate the series snapshot: --series, else the root's, else luthen's export tree.

    Returns:
        The snapshot's path; luthen's export tree when the root holds none (nemik:W1287).

    """
    if args.series:
        return args.series
    here = args.root / "luthen-series.json"
    return here if here.exists() else EXPORT_TREE / "luthen-series.json"


class Options(argparse.Namespace):
    """nemik-wake's parsed command line, typed so each option reads as its own type."""

    root: Path
    liveness: str | None
    all: bool
    json: bool
    nudge: bool
    nudges_state: Path
    alarms: bool
    since: str | None
    until: str | None
    series_lines: bool
    series_only: bool
    only: bool
    repo: list[str] | None
    series: Path | None
    series_max_age: int


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """Run nemik-wake: print the roster of workstreams, or with --alarms the alarms that fired.

    The roster lists the workstreams that are not awake (all with --all) plus the operator row.
    --nudge keeps only rows due a nudge, or only alarms not yet delivered, and records them in
    the nudges state file. --json prints machine-readable output.

    Args:
        argv: the command line, or None for sys.argv.
        g: a graph to read instead of surveying the root.

    """
    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(
        prog="nemik-wake", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--liveness", help="loop_liveness JSON file, or - for stdin")
    ap.add_argument("--all", action="store_true", help="include awake workstreams")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--nudge",
        action="store_true",
        help="print only rows due a nudge now (backoff/dedup via --nudges-state); with --alarms, "
        "only firings not yet delivered",
    )
    ap.add_argument("--nudges-state", type=Path, default=nudges_path())
    ap.add_argument(
        "--alarms",
        action="store_true",
        help="list alarms that fired on open waypoints in [--since, --until) (nemik:W149)",
    )
    ap.add_argument(
        "--since", help="ISO-8601 instant (default: 15 minutes before --until)"
    )
    ap.add_argument("--until", help="ISO-8601 instant (default: now)")
    ap.add_argument(
        "--series-lines",
        action="store_true",
        help="print one line per repo, <repo> <verdict> <as_of>, from luthen's series snapshot",
    )
    ap.add_argument(
        "--series",
        type=Path,
        help="the snapshot (default: <root>/luthen-series.json)",
    )
    ap.add_argument(
        "--series-max-age",
        type=int,
        default=900,
        help="seconds after which the series snapshot is refused (default 900)",
    )
    ap.add_argument(
        "--series-only",
        action="store_true",
        help="read the series alone, loading no queue; the repos are its own plus --repo",
    )
    ap.add_argument(
        "--only",
        action="store_true",
        help="with --series-only: print just the repos named with --repo",
    )
    ap.add_argument(
        "--repo",
        action="append",
        help="a repo to report even if the series has none (repeat); it reads no sample",
    )
    args = ap.parse_args(argv, namespace=Options())
    if args.series_only:
        series_report(
            args.repo or [], series_path(args), args.series_max_age, only=args.only
        )
        return
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    if args.series_lines:
        series_report(
            workstreams(g) + (args.repo or []), series_path(args), args.series_max_age
        )
        return
    live, source = read_liveness(args.root, args.liveness)
    if args.alarms:
        from datetime import timedelta

        until = datetime.fromisoformat(args.until) if args.until else datetime.now(UTC)
        since = (
            datetime.fromisoformat(args.since)
            if args.since
            else until - timedelta(minutes=15)
        )
        fired = fired_alarms(g, since.astimezone(UTC), until.astimezone(UTC), live)
        if args.nudge:
            # nemik:W167: alarms go out through the nudge path, so each firing is delivered once
            # (W166's key) in the same state file the repo nudges use.
            seen = _read_seen(args.nudges_state)
            fired = undelivered(fired, seen)
            _write_seen(args.nudges_state, seen)
        if args.json:
            print(
                json.dumps(
                    {
                        "liveness": source,
                        "since": since.isoformat(),
                        "until": until.isoformat(),
                        "alarms": fired,
                    },
                    indent=2,
                )
            )
            return
        print(
            f"alarms fired {since.isoformat()} .. {until.isoformat()} (liveness: {source})"
        )
        for a in fired:
            occ = f" [{a['recurrence_id']}]" if a["recurrence_id"] else ""
            what = f"ERROR {a['error']}" if a.get("error") else a["title"][:60]
            print(
                f"  {a['at'] or '-':20} {a['state']:7} {a['ref']:28}{occ} {a['trigger']:22} {what}"
            )
            if a.get("message"):
                print(f"      send: {a['message'].splitlines()[0]}")
        return
    from datetime import timedelta

    end = datetime.now(UTC)
    rows = [
        r
        for r in roster(
            g, live, alarms=fired_alarms(g, end - timedelta(minutes=15), end, live)
        )
        if args.all or r["state"] != "awake"
    ]
    if args.nudge:
        seen = _read_seen(args.nudges_state)
        rows = due_nudges(rows, seen)
        _write_seen(args.nudges_state, seen)
    if args.json:
        print(
            json.dumps(
                {"liveness": source, "roster": rows, "operator": operator_row(g)},
                indent=2,
            )
        )
        return
    print(f"liveness: {source}")
    for r in rows:
        print(
            f"\n{r['state'].upper():7} {r['repo']}  ({len(r['waiting'])} waiting; last tick {r['last_tick'] or 'none'})"
        )
        for w in r["waiting"]:
            claim = (
                ", ".join(w["claimed_by"])
                or f"waiting on {r['repo']}: claim with --enables {w['blocked']}"
            )
            print(f"          {w['blocked']:28} {claim:22} {w['title'][:60]}")
    op = operator_row(g)
    print(f"\nYOU     operator  ({len(op['waiting'])} need you: nemik-operator)")
    # nemik:W298: the five heaviest, with the demand waiting behind each
    for w in op["waiting"][:5]:
        print(f"  {w['salience']:6.1f} {w['blocked']:28} {w['title'][:60]}")
