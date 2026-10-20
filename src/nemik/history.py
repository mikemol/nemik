# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W267: how a workstream's graph changed between two points in its git history.

nemik-history reads each repo's committed `.claude/paths-forward.json` at two revisions (or the
last commit before two dates) and prints what moved: minted, closed, dropped, status flips, edge
changes, and the new blocks on other workstreams (W267); `--time-in-state` sums each open card's
time per status (W268) and `--weekly` rolls the history up by ISO week (W269). It reads history
only, so it works backwards over everything ever committed; nothing here writes or needs new data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import zlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from nemik.cachestore import user_dir
from nemik.cardevents import Event, events_of
from nemik.check import LEDGER, QUEUE, default_root, workstream_files
from nemik.climate import leads_by_repo, open_ages, waits_of
from nemik.forecastshingle import HORIZONS, issue, shingle_rows
from nemik.verify import score_shingle

WAIT_QUANTILE = 0.9
COMMIT_GRAIN_DAYS = 1.0  # backfilled history is commit-grain; docs/weather-questions.md
# the modes that read a whole history rather than diff two points of it, named by their option
SERIES_MODES = (
    "time_in_state",
    "weekly",
    "density",
    "events",
    "waits",
    "forecast",
    "score",
)


SHINGLE_COLUMNS = 5  # issued, station, lead, age, chance


def shingle_lines(text: str) -> list[list[str]]:
    """Read the rows of a stored shingle out of its text (nemik:W759).

    Returns:
        The tab-split lines that are rows of five fields; a blank or a wrapper's status line is
        not one and is skipped.

    """
    split = (line.split("\t") for line in text.splitlines())
    return [row for row in split if len(row) == SHINGLE_COLUMNS]


def first_done(events: list[Event]) -> dict[str, str]:
    """Find when each card was first done, from the events.

    Returns:
        {station: the stamp of its first status event to done}.

    """
    out: dict[str, str] = {}
    for station, stamp, what, _, now, _ in events:
        if what == "status" and now == "done" and station not in out:
            out[station] = stamp
    return out


def score_rows(
    rows: list[list[str]], events: list[Event], now: str
) -> dict[str, float]:
    """Score stored shingle rows against the events at the commit-grain floor (nemik:W759).

    Returns:
        {lead: Brier score}, only for leads the truth's grain allows.

    """
    return score_shingle(rows, first_done(events), now, COMMIT_GRAIN_DAYS)


def is_series(args: argparse.Namespace, *, extra: tuple[str, ...] = ()) -> bool:
    """Say whether the options ask for a mode that reads a whole history.

    Returns:
        True when any of SERIES_MODES, or of `extra`, is set.

    """
    return any(getattr(args, mode) for mode in SERIES_MODES + extra)


def forecast_rows(events: list[Event], moment: str) -> list[list[str]]:
    """Issue the forecast for every open card at one moment, as shingle rows (nemik:W747).

    Each open card's chances at +1, +3 and +7 days, from the lead times of its repo's cards done by
    then; one row per card and lead.

    Returns:
        The rows: issue time, station, lead, age in days, chance.

    """
    leads = leads_by_repo(events, moment)
    rows: list[list[str]] = []
    for station, age in sorted(open_ages(events, moment).items()):
        chances = issue(leads.get(station.partition(":")[0], []), age, HORIZONS)
        rows.extend(shingle_rows(moment, station, age, chances))
    return rows


def waits(
    events: list[Event],
) -> dict[str, dict[str, float]]:
    """Summarize finished stints per status from events (nemik:W753).

    Returns:
        {status: {n, median_days, p90_days}}.

    """
    return {
        status: {
            "n": len(days),
            "median_days": round(days[len(days) // 2], 2),
            "p90_days": round(days[int(WAIT_QUANTILE * (len(days) - 1))], 2),
        }
        for status, days in waits_of(events).items()
    }


def backfill(repo: str, repo_dir: Path, since: str | None = None) -> list[Event]:
    """Walk a repo's committed queue and list every change as an event (nemik:W744).

    Each commit of the queue file is compared with the one before it (the first with an empty
    queue, so it mints every card then in it). The fields are the slim queue's: status, blocker
    kind, blockers and enables; title and evidence edits are not events here.

    Returns:
        The events, oldest first, each naming its commit.

    """
    out: list[Event] = []
    before: QueueDoc = {}
    if since:
        before = slim(queue_at(repo_dir, resolve(repo_dir, since)))
    for sha, at, queue in commit_snapshots(repo_dir, since):
        out.extend(events_of(repo, before, queue, sha, at.isoformat()))
        before = queue
    return out


QUEUE_PATH = f".claude/{QUEUE}"
MIN_LANDINGS = 3  # nemik:W616: fewer cited commits than this teach no land interval
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")
_CROSS = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*):W[1-9][0-9]*")

# nemik:W732: a committed queue as the history readers see it. The fields they read are strings and
# lists of strings; a parsed queue carries more (evidence, titles), which `slim` drops.
Waypoint = dict[str, str | list[str]]
QueueDoc = dict[str, list[Waypoint]]

# nemik:W729: the slim queue of each git blob, by blob id. A blob never changes, so the answer is
# kept for the process and, compressed, under the user cache directory: a later build reads and
# parses only the blobs it has not seen. Best effort: a cache it cannot write is just a cold read.
_SLIM: dict[str, QueueDoc] = {}


def _slim_path(oid: str) -> Path:
    # slim2: the slim queue grew fields (W752), so a file of the older shape must not be read
    return user_dir() / "slim2" / f"{oid}.z"


def _slim_known(oid: str) -> bool:
    if oid in _SLIM:
        return True
    try:
        _SLIM[oid] = json.loads(zlib.decompress(_slim_path(oid).read_bytes()))
    except OSError:
        return False
    except zlib.error:
        return False
    except ValueError:
        return False
    return True


def _slim_keep(oid: str, queue: QueueDoc) -> None:
    _SLIM[oid] = queue
    path = _slim_path(oid)
    tmp = path.with_suffix(f".{os.getpid()}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(zlib.compress(json.dumps(queue).encode()))
        tmp.replace(path)
    except OSError:
        return


@dataclass
class Diff:
    """What changed in one repo's queue between two states."""

    minted: list[str] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    flips: list[tuple[str, str, str]] = field(default_factory=list)
    edges_added: list[tuple[str, str, str]] = field(default_factory=list)
    edges_removed: list[tuple[str, str, str]] = field(default_factory=list)
    new_cross_blocks: list[tuple[str, str]] = field(default_factory=list)


def _status(queue: QueueDoc) -> dict[str, str]:
    return {
        str(w["symbol"]): str(w.get("status", "")) for w in queue.get("waypoints", [])
    }


def _dropped(queue: QueueDoc) -> set[str]:
    return {str(r["symbol"]) for r in queue.get("residue", [])}


def _edges(queue: QueueDoc) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for w in queue.get("waypoints", []):
        sym = str(w["symbol"])
        out |= {("enables", sym, t) for t in w.get("enables", [])}
        out |= {("waits", sym, b) for b in w.get("blocked_on", [])}
    return out


def _number(symbol: str) -> tuple[int, int, str]:
    """A sort key: W<n> by number, then anything that is not a W<n> (an old or foreign symbol in a
    committed queue, such as luthen's `R-amtool`) after them by name, never an error."""
    digits = symbol.removeprefix("W")
    if symbol.startswith("W") and digits.isdigit():
        return (0, int(digits), "")
    return (1, 0, symbol)


def diff(old: QueueDoc, new: QueueDoc) -> Diff:
    """The changes from `old` to `new`, both parsed queues (an empty dict is a repo with no queue)."""
    before, after = _status(old), _status(new)
    known = set(before) | _dropped(old)
    d = Diff()
    d.minted = sorted(
        (s for s in set(after) | _dropped(new) if s not in known), key=_number
    )
    d.closed = sorted(
        (s for s, st in after.items() if st == "done" and before.get(s) != "done"),
        key=_number,
    )
    d.dropped = sorted(_dropped(new) - _dropped(old), key=_number)
    d.flips = sorted(
        (
            (s, before[s], st)
            for s, st in after.items()
            if s in before and before[s] != st and st != "done"
        ),
        key=lambda f: _number(f[0]),
    )
    old_edges, new_edges = _edges(old), _edges(new)
    d.edges_added = sorted(new_edges - old_edges)
    d.edges_removed = sorted(old_edges - new_edges)
    d.new_cross_blocks = sorted(
        (s, b)
        for kind, s, b in d.edges_added
        if kind == "waits" and _CROSS.fullmatch(b.strip())
    )
    return d


def _run(repo: Path, args: tuple[str, ...], stdin: bytes = b"") -> bytes | None:
    # nemik:W572: no git binary is no history, like a directory that is not a repository. The
    # image's final stage carries no git (only its test stage does), and the snapshot builder of
    # the pod (nemik-serve --publish) reaches this, so a missing binary must not stop a publish.
    try:
        run = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            check=False,
            input=stdin or None,
        )
    except OSError:
        return None
    return run.stdout if run.returncode == 0 else None


def _git(repo: Path, *args: str) -> str | None:
    out = _run(repo, args)
    if out is None:
        return None
    return out.decode()


def resolve(repo: Path, spec: str | None) -> str | None:
    """A revision for `spec`: a date means the last commit before it, anything else is a rev.

    None means there is no such point (before the repo's first commit): an empty queue.
    """
    if spec is None:
        return "HEAD"
    if _DATE.fullmatch(spec):
        # git reads a bare date as that day at the CURRENT time of day, so "--from 2026-10-11" run in
        # the evening meant the evening of the 11th: pin it to the start of the day (nemik:W318).
        when = f"{spec}T00:00" if len(spec) == len("YYYY-MM-DD") else spec
        out = _git(repo, "rev-list", "-1", f"--before={when}", "HEAD")
        return (out or "").strip() or None
    return spec


KEPT = (
    "symbol",
    "status",
    "blocked_kind",
    "enables",
    "blocked_on",
    "manifest",
    "size_class",
    "weight",
    "touches",
)
# the long text fields, kept as their length: the bits a forecast needs are that they changed and
# by how much (docs/weather-questions.md), and they are half the bytes of a committed queue
LENGTHS = {"evidence": "evidence_len", "next_bounded_step": "next_len"}


def _plain(value: str | list[str] | int | None) -> str | list[str]:
    """Write a queue value as a string or a list of strings.

    A queue stores numbers (weight) and nulls (an unset field) beside text; the events and the
    slim cache carry text only.

    Returns:
        The value as text, a list as a list of text, a null or empty value as "".

    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [str(item) for item in value]
    return str(value) if value or value == 0 else ""


def slim(queue: QueueDoc) -> QueueDoc:
    """Keep only what the history readers use of a parsed queue (nemik:W731, W752).

    They read each waypoint's symbol, status, blocked_kind, enables, blocked_on, manifest,
    size_class, weight and touches, and each residue entry's symbol, all as text; and, for the
    long text fields, how long they are. Evidence and titles are half the bytes of a committed
    queue and no reader of history looks at their text.

    Returns:
        A queue with those fields and no others.

    """
    cards = []
    for w in queue.get("waypoints", []):
        card = {key: _plain(w[key]) for key in KEPT if key in w}
        for source, name in LENGTHS.items():
            size = len(str(_plain(w.get(source, ""))))
            if size:
                card[name] = str(size)
        cards.append(card)
    return {
        "waypoints": cards,
        "residue": [
            {"symbol": r["symbol"]} for r in queue.get("residue", []) if "symbol" in r
        ],
    }


def _blob_ids(repo: Path, revs: list[str]) -> list[str]:
    """Name the queue file's git blob at each of `revs` with one git process, '' where none.

    Returns:
        One blob id per rev, in order.

    """
    if not revs:
        return []
    ask = "".join(f"{rev}:{QUEUE_PATH}\n" for rev in revs).encode()
    data = _run(repo, ("cat-file", "--batch-check"), ask)
    if data is None:
        return [""] * len(revs)
    seen = [line.split(" ") for line in data.decode().splitlines()]
    return [parts[0] if parts[1:2] == ["blob"] else "" for parts in seen]


def queues_text_at(repo: Path, revs: list[str]) -> list[str]:
    """Read the queue file's text at each of `revs` with one git process, '' where there is none.

    nemik:W725: a cold document build ran `git show` once per queue commit (3,931 forks, 28% of the
    build). `git cat-file --batch` answers `<rev>:<path>` lines on stdin with `<oid> blob <size>`
    then the bytes, or `<spec> missing`.

    Returns:
        One text per rev, in order.

    """
    return _read_blobs(repo, [f"{rev}:{QUEUE_PATH}" for rev in revs])


def _read_blobs(repo: Path, specs: list[str]) -> list[str]:
    """Read the text of each git object named by `specs` with one process, '' where missing.

    Returns:
        One text per spec, in order.

    """
    blank = [""] * len(specs)
    if not specs:
        return blank
    ask = "".join(f"{spec}\n" for spec in specs).encode()
    data = _run(repo, ("cat-file", "--batch"), ask)
    if data is None:
        return blank
    at = 0
    out: list[str] = []
    for _ in specs:
        end = data.index(b"\n", at)
        head = data[at:end].split(b" ")
        at = end + 1
        if head[1:2] == [b"blob"]:
            size = int(head[2])
            out.append(data[at : at + size].decode())
            at += size + 1
        else:
            out.append("")
    return out


def queue_at(repo: Path, rev: str | None, known: str = "") -> QueueDoc:
    """The parsed queue as committed at `rev`; empty when there is none then.

    `known` is the file's text at `rev` when a batch read already has it (nemik:W725).
    """
    if rev is None:
        return {}
    text = known or _git(repo, "show", f"{rev}:{QUEUE_PATH}")
    return json.loads(text) if text else {}


def staged_paths(repo: Path) -> list[str]:
    """List the files staged in a repo's index: the ones a commit in flight already holds.

    Args:
        repo: The repo's working directory.

    Returns:
        The staged repo-relative paths; empty when nothing is staged or git is unreadable.

    """
    out = _git(repo, "diff", "--cached", "--name-only")
    return out.split() if out else []


def tracked_files(repo: Path) -> set[str]:
    """List the files git tracks in a repo (nemik:W613 --propose resolves bare names against them).

    Args:
        repo: The repo's working directory.

    Returns:
        The tracked repo-relative paths; empty when git is unreadable.

    """
    out = _git(repo, "ls-files")
    return set(out.split()) if out else set()


def cited_files(repo: Path, symbol: str) -> list[str]:
    """List the files the commits citing a card touched (nemik:W613 --propose).

    Args:
        repo: The repo's working directory.
        symbol: The card's symbol, as a `Waypoint: W<n>` trailer names it.

    Returns:
        The distinct repo-relative paths of its newest 20 citing commits, sorted; empty when none.

    """
    out = _git(
        repo,
        "log",
        "-E",
        f"--grep=^Waypoint: {symbol}$",
        "--name-only",
        "--format=",
        "-n",
        "20",
    )
    return sorted(set(out.split())) if out else []


def close_rate(repo: Path, since: str, days: int) -> float | None:
    """Measure how fast a repo closes cards, per day (nemik:W618).

    Args:
        repo: The repo's working directory.
        since: A local `YYYY-MM-DDTHH:MM:SS` instant, `days` days back.
        days: The length of the window in days.

    Returns:
        Cards the committed queue closed since `since`, per day, or None without a committed queue.

    """
    head: QueueDoc = queue_at(repo, "HEAD")
    if not head:
        return None
    start: QueueDoc = queue_at(repo, resolve(repo, since))
    return len(diff(start, head).closed) / days


def citing_epochs(repo: Path, symbol: str) -> list[int] | None:
    """List when commits cited a card, newest first (nemik:W616).

    Args:
        repo: The repo's working directory.
        symbol: The card's symbol, as a `Waypoint: W<n>` trailer names it.

    Returns:
        The commit times in epoch seconds (the newest 200), or None without readable git history.

    """
    out = _git(
        repo, "log", "-E", f"--grep=^Waypoint: {symbol}$", "--format=%ct", "-n", "200"
    )
    if out is None:
        return None
    return [int(word) for word in out.split() if word.isdigit()]


def land_interval(repo: Path) -> int | None:
    """Learn how often the repo lands cited work, in seconds (nemik:W616).

    Args:
        repo: The repo's working directory.

    Returns:
        The median gap between its newest 50 commits that carry a Waypoint trailer, or None when
        the history is unreadable or holds fewer than three such commits.

    """
    out = _git(repo, "log", "-E", "--grep=^Waypoint: ", "--format=%ct", "-n", "50")
    if out is None:
        return None
    times = sorted(int(word) for word in out.split() if word.isdigit())
    if len(times) < MIN_LANDINGS:
        return None
    gaps = [times[i + 1] - times[i] for i in range(len(times) - 1)]
    return int(statistics.median(gaps))


def reopened_since(repo: Path, since: str) -> int | None:
    """Count the cards that went from done back to open after a point in time (nemik:W355).

    A reopened or re-minted card is a change that failed, the DORA change-failure signal.

    Args:
        repo: The repo's working directory.
        since: A local `YYYY-MM-DDTHH:MM:SS` instant.

    Returns:
        How many done-to-open transitions the committed queue shows in the window, or None when the
        directory has no committed queue.

    """
    head: QueueDoc = queue_at(repo, "HEAD")
    if not head:
        return None
    start: QueueDoc = queue_at(repo, resolve(repo, since))
    commits: list[tuple[datetime, QueueDoc]] = snapshots(repo, since)
    after: list[dict[str, str]] = [_status(q) for _, q in commits]
    prior = _status(start)
    reopened = 0
    for current in after:
        reopened += sum(
            1 for s, st in current.items() if st != "done" and prior.get(s) == "done"
        )
        prior = current
    return reopened


def commits_since(repo: Path, since: str) -> int | None:
    """Count the commits on HEAD after a point in time (nemik:W355: a push is a deploy).

    Args:
        repo: The repo's working directory.
        since: A local `YYYY-MM-DDTHH:MM:SS` instant.

    Returns:
        The number of commits, or None when the directory has no readable git history.

    """
    out = _git(repo, "rev-list", "--count", f"--since={since}", "HEAD")
    return int(out) if out and out.strip().isdigit() else None


Snapshot = tuple[datetime, QueueDoc]


def snapshots(
    repo: Path, since: str | None = None, *, full: bool = False
) -> list[Snapshot]:
    """Every committed state of the queue, oldest first, as (commit time, parsed queue).

    Returns:
        (commit time, queue) per commit that touched the queue file; see `commit_snapshots`.

    """
    return [(at, queue) for _, at, queue in commit_snapshots(repo, since, full=full)]


def commit_snapshots(
    repo: Path, since: str | None = None, *, full: bool = False
) -> list[tuple[str, datetime, QueueDoc]]:
    """Every committed state of the queue, oldest first, with the commit that made it.

    `since` is a revision or date (see `resolve`): only commits after it. The queues are slim (see
    `slim`) and read by blob id: a blob already seen, this process or an earlier one, is neither
    read from git nor parsed again (nemik:W729). `full` asks for the whole queue of every commit
    instead, read through one `git cat-file --batch` (nemik:W725); churn needs attributes.

    Returns:
        (commit sha, commit time, queue) per commit that touched the queue file.

    """
    start = resolve(repo, since) if since else None
    span = f"{start}..HEAD" if start else "HEAD"
    log = _git(repo, "log", "--format=%H%x09%cI", "--reverse", span, "--", QUEUE_PATH)
    rows = [line.partition("\t") for line in (log or "").splitlines()]
    shas = [sha for sha, _, _ in rows]
    if full:
        texts = queues_text_at(repo, shas)
        queues = [
            queue_at(repo, sha, text) for sha, text in zip(shas, texts, strict=True)
        ]
    else:
        oids = _blob_ids(repo, shas)
        need = sorted({oid for oid in oids if oid and not _slim_known(oid)})
        for oid, text in zip(need, _read_blobs(repo, need), strict=True):
            _slim_keep(oid, slim(json.loads(text) if text else {}))
        queues = [_SLIM.get(oid, {}) for oid in oids]
    return [
        (sha, datetime.fromisoformat(stamp), queue)
        for (sha, _, stamp), queue in zip(rows, queues, strict=True)
        if queue
    ]


def time_in_state(snaps: list[Snapshot], now: datetime) -> dict[str, dict[str, float]]:
    """Seconds each waypoint spent in each status: a commit's state holds until the next commit
    (the last one until `now`)."""
    totals: dict[str, dict[str, float]] = {}
    for i, (at, queue) in enumerate(snaps):
        end = snaps[i + 1][0] if i + 1 < len(snaps) else now
        held = (end - at).total_seconds()
        for symbol, status in _status(queue).items():
            per = totals.setdefault(symbol, {})
            per[status] = per.get(status, 0.0) + held
    return totals


def _flow_efficiency(
    closed: list[str], spent: dict[str, dict[str, float]]
) -> float | None:
    """Working time over all live time (ready, working, blocked) summed over `closed`, or None."""
    active = sum(spent.get(s, {}).get("working", 0.0) for s in closed)
    live = sum(
        spent.get(s, {}).get(k, 0.0)
        for s in closed
        for k in ("ready", "working", "blocked")
    )
    return round(active / live, 3) if live else None


def weekly(snaps: list[Snapshot]) -> list[dict]:
    """One row per ISO week that saw a commit: opened and closed that week, how much of what was
    open at the week's last commit was blocked, and the longest-running block then.

    A block's age runs from the commit where the card last entered `blocked`.
    """
    weeks: dict[tuple[int, int], list[Snapshot]] = {}
    for at, queue in snaps:
        iso = at.isocalendar()
        weeks.setdefault((iso.year, iso.week), []).append((at, queue))
    rows: list[dict] = []
    before: dict = {}
    blocked_since: dict[str, datetime] = {}
    born: dict[str, datetime] = {}
    done_at: dict[str, datetime] = {}
    # nemik:W328: time each card spent in each status over the whole history, for flow efficiency.
    spent = time_in_state(snaps, snaps[-1][0] if snaps else datetime.now(UTC))
    on_operator: set[str] = set()
    for (year, week), inside in sorted(weeks.items()):
        finished: list[float] = []
        closed_now: list[str] = []
        # nemik:W357: operator asks, a card entering or leaving blocked_kind human, counted per week.
        asked, answered = 0, 0
        for at, queue in inside:
            now_on = {
                str(w["symbol"])
                for w in queue.get("waypoints", [])
                if w.get("status") == "blocked" and w.get("blocked_kind") == "human"
            }
            asked += len(now_on - on_operator)
            answered += len(on_operator - now_on)
            on_operator = now_on
            for symbol, status in _status(queue).items():
                born.setdefault(symbol, at)
                if status == "done" and symbol not in done_at:
                    done_at[symbol] = at
                    finished.append((at - born[symbol]).total_seconds() / 86400)
                    closed_now.append(symbol)
                if status == "blocked":
                    blocked_since.setdefault(symbol, at)
                else:
                    blocked_since.pop(symbol, None)
        end_at, end = inside[-1]
        change = diff(before, end)
        at_end = _status(end)
        open_cards = [s for s, st in at_end.items() if st not in ("done", "dropped")]
        blocked = [s for s in open_cards if at_end[s] == "blocked"]
        oldest = min(blocked, key=lambda s: blocked_since[s], default=None)
        rows.append(
            {
                "week": f"{year}-W{week:02d}",
                "opened": len(change.minted),
                "closed": len(change.closed),
                # nemik:W315: median days from a card's first commit to the commit that closed it,
                # over the cards that closed this week (None when none did).
                "lead_time_days": round(statistics.median(finished), 1)
                if finished
                else None,
                "open": len(open_cards),
                # nemik:W325 (Little's law, L = lambda W): utilization is arrivals over departures
                # (above 1 the queue grows); implied_wait_days is open cards over the weekly close
                # rate, how long a new card waits at this week's pace.
                "utilization": round(len(change.minted) / len(change.closed), 2)
                if change.closed
                else None,
                "implied_wait_days": round(len(open_cards) / len(change.closed) * 7, 1)
                if change.closed
                else None,
                # nemik:W328: working time over (ready + working + blocked) time, for the cards that
                # closed this week; None when none had any, low until agents mark the working state.
                "flow_efficiency": _flow_efficiency(closed_now, spent),
                "blocked_share": round(len(blocked) / len(open_cards), 3)
                if open_cards
                else 0.0,
                "operator_asked": asked,
                "operator_answered": answered,
                "operator_open": len(on_operator),
                # Little's law on the operator alone: open asks over the weekly answer rate.
                "operator_wait_days": round(len(on_operator) / answered * 7, 1)
                if answered
                else None,
                "oldest_blocked": oldest,
                "oldest_blocked_days": round(
                    (end_at - blocked_since[oldest]).total_seconds() / 86400, 1
                )
                if oldest
                else None,
            }
        )
        before = end
    return rows


BASELINE_PATH = ".claude/baseline"


def baseline_spec(repo: Path, spec: str | None) -> str | None:
    """nemik:W318: the baseline to measure from: `spec` when given, else the first word of the repo's
    declared `.claude/baseline` file (a revision or a date), else None (no baseline declared)."""
    if spec:
        return spec
    declared = repo / BASELINE_PATH
    if declared.is_file():
        words = declared.read_text(encoding="utf-8").split()
        return words[0] if words else None
    return None


def variance(base: dict, now: dict) -> dict:
    """nemik:W318: planned versus actual since a baseline. The plan is the cards open at the baseline:
    how many are now closed, dropped, or still open. The unplanned is every card minted since, split by
    how it was minted (an interrupt, a tick, or not recorded). Both arguments are parsed queues."""
    planned = {
        s
        for s, st in _status(base).items()
        if st not in ("done", "dropped") and s not in _dropped(base)
    }
    after, gone = _status(now), _dropped(now)
    closed = sorted((s for s in planned if after.get(s) == "done"), key=_number)
    dropped = sorted((s for s in planned if s in gone), key=_number)
    still = sorted(
        (s for s in planned if s not in gone and after.get(s) not in (None, "done")),
        key=_number,
    )
    known = set(_status(base)) | _dropped(base)
    minted_during = {
        w["symbol"]: w.get("minted_during") or "unrecorded"
        for w in now.get("waypoints", [])
    }
    added: dict[str, list[str]] = {}
    for s in sorted((s for s in set(after) | gone if s not in known), key=_number):
        added.setdefault(minted_during.get(s, "unrecorded"), []).append(s)
    return {
        "planned": len(planned),
        "closed": closed,
        "dropped": dropped,
        "still_open": still,
        "added": added,
        "done_share": round(len(closed) / len(planned), 3) if planned else None,
    }


def shape_drift(base: dict, now: dict) -> dict:
    """nemik:W349: how far the graph's SHAPE moved since a baseline, beside `variance`'s counts.
    Edges added and removed (enables and waits), the planned cards (open at the baseline) whose
    title changed (re-scoped) or whose own edges changed (re-wired), and the share of planned cards
    touched either way."""
    planned = {
        s
        for s, st in _status(base).items()
        if st not in ("done", "dropped") and s not in _dropped(base)
    }
    old_e, new_e = _edges(base), _edges(now)
    titles = {w["symbol"]: w.get("title", "") for w in base.get("waypoints", [])}
    retitled = sorted(
        (
            w["symbol"]
            for w in now.get("waypoints", [])
            if w["symbol"] in planned and w.get("title", "") != titles.get(w["symbol"])
        ),
        key=_number,
    )
    changed = old_e ^ new_e
    rewired = sorted({s for _, s, _ in changed if s in planned}, key=_number)
    touched = set(retitled) | set(rewired)
    return {
        "edges_added": len(new_e - old_e),
        "edges_removed": len(old_e - new_e),
        "retitled": retitled,
        "rewired": rewired,
        "touched_share": round(len(touched) / len(planned), 3) if planned else None,
    }


def render(repo: str, d: Diff) -> str:
    lines = [
        f"{repo}: {len(d.minted)} minted, {len(d.closed)} closed, {len(d.dropped)} dropped"
    ]

    def block(title: str, rows: list[str]) -> None:
        if rows:
            lines.append(f"  {title}: " + ", ".join(rows))

    block("minted", d.minted)
    block("closed", d.closed)
    block("dropped", d.dropped)
    block("flipped", [f"{s} {a}->{b}" for s, a, b in d.flips])
    # A blocked_on entry may be a paragraph (an operator ask): the line names it, --json has it whole.
    block("edges added", [f"{s} {k} {t[:48]}" for k, s, t in d.edges_added])
    block("edges removed", [f"{s} {k} {t[:48]}" for k, s, t in d.edges_removed])
    block(
        "new blocks on other workstreams",
        [f"{s} on {b}" for s, b in d.new_cross_blocks],
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """nemik-history: what changed in a workstream's graph between two revisions or dates."""
    ap = argparse.ArgumentParser(
        prog="nemik-history", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("repos", nargs="*", help="repos under --root; none with --all")
    ap.add_argument("--all", action="store_true", help="every workstream under --root")
    ap.add_argument(
        "--from",
        dest="start",
        default=None,
        help="a revision or a date (YYYY-MM-DD[THH:MM]); a date is the last commit before it",
    )
    ap.add_argument("--to", default=None, help="as --from; default HEAD")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument("--json", action="store_true")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--time-in-state",
        action="store_true",
        help="per open waypoint, the time spent in each status over the whole history (W268)",
    )
    mode.add_argument(
        "--weekly",
        action="store_true",
        help="per ISO week: opened, closed, blocked share, oldest block (W269)",
    )
    mode.add_argument(
        "--toil",
        action="store_true",
        help="per ISO week: ledger activity by effort class and the interrupt share (W314)",
    )
    mode.add_argument(
        "--churn",
        action="store_true",
        help="how often a poll of the fleet's queues finds them changed, and how (identical, "
        "attribute-only, status flip, structural), sampled over --from..now, default a week (W495)",
    )
    mode.add_argument(
        "--events",
        action="store_true",
        help="every change to a card in the queue history, one event a line: station, time, "
        "field, from, to, commit (W744)",
    )
    mode.add_argument(
        "--score",
        metavar="FILE",
        help="score a stored shingle (the rows --forecast printed) against the events: the Brier "
        "score per lead, leaving out leads finer than the commit grain (W759)",
    )
    mode.add_argument(
        "--forecast",
        action="store_true",
        help="issue the forecast now for every open card: the chance it is done within +1, +3 and "
        "+7 days, one shingle row a line (W747)",
    )
    mode.add_argument(
        "--waits",
        action="store_true",
        help="per repo and status: how many stints in it finished, and their median and "
        "ninetieth-percentile length in days (W753)",
    )
    mode.add_argument(
        "--density",
        action="store_true",
        help="per repo: queue-file commits a day over --from..now (default 7 days) and "
        "the longest gap between two, in hours (W739)",
    )
    mode.add_argument(
        "--baseline",
        nargs="?",
        const="",
        default=None,
        metavar="REV_OR_DATE",
        help="planned versus actual since a baseline: the cards open then, closed, dropped or "
        f"still open now, and the cards added since by how they were minted; without a value, "
        f"the repo's declared {BASELINE_PATH} (W318)",
    )
    args = ap.parse_args(argv)
    dirs = {r: p.parents[1] for r, p in workstream_files(args.root, QUEUE)}
    names = sorted(dirs) if args.all else args.repos
    series = is_series(args, extra=("toil", "churn")) or args.baseline is not None
    if not names or (args.start is None and not series):
        ap.error("name the repos (or --all) and a --from")
    for name in names:
        if name not in dirs:
            print(f"ERROR: no workstream {name} under {args.root}", file=sys.stderr)
            return 2
    if args.churn:
        from nemik.churn import run

        return run(dirs, names, args.start, args.json)
    if args.toil:
        return _toil(args, names, dirs)
    if args.baseline is not None:
        return _baseline(args, names, dirs)
    if is_series(args):
        return _series(args, names, dirs)
    out: dict[str, Diff] = {}
    for name in names:
        repo = dirs[name]
        old = queue_at(repo, resolve(repo, args.start))
        new = queue_at(repo, resolve(repo, args.to))
        out[name] = diff(old, new)
    if args.json:
        print(json.dumps({r: asdict(d) for r, d in out.items()}, indent=1))
    else:
        print("\n".join(render(r, d) for r, d in out.items()))
    return 0


def longest_gap_hours(stamps: list[datetime]) -> float:
    """Measure the longest stretch between two consecutive commits (nemik:W739).

    Returns:
        The gap in hours, 0.0 for fewer than two commits.

    """
    ordered = sorted(stamps)
    gaps = [
        (ordered[i + 1] - ordered[i]).total_seconds() / 3600
        for i in range(len(ordered) - 1)
    ]
    return round(max(gaps), 1) if gaps else 0.0


def ledger_lines_since(ledger: Path, cutoff: str) -> int:
    """Count the ledger lines stamped at or after `cutoff` (nemik:W741).

    A ledger line starts with its UTC stamp, 2026-09-26T18:54:10Z, which sorts as text.

    Returns:
        The number of such lines, 0 when the ledger cannot be read.

    """
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line[:20] >= cutoff)


def _density(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """Print how often each repo commits its queue file, the longest gap and its ledger rate."""
    since = args.start or "7.days.ago"
    days = 7.0
    if args.start:
        began = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
        days = max((datetime.now(UTC) - began).total_seconds() / 86400, 1 / 24)
    # nemik:W741: the ledger is written live, so its lines per day say what the commits miss
    cutoff = datetime.fromtimestamp(
        datetime.now(UTC).timestamp() - days * 86400, UTC
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: dict[str, dict[str, float]] = {}
    for name in names:
        out = _git(
            dirs[name], "log", f"--since={since}", "--format=%cI", "--", QUEUE_PATH
        )
        stamps = [datetime.fromisoformat(line) for line in (out or "").split()]
        lines = ledger_lines_since(dirs[name] / ".claude" / LEDGER, cutoff)
        rows[name] = {
            "commits": len(stamps),
            "per_day": round(len(stamps) / days, 1),
            "longest_gap_hours": longest_gap_hours(stamps),
            "ledger_lines": lines,
            "ledger_per_day": round(lines / days, 1),
        }
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=1) + "\n")
        return 0
    for name, r in rows.items():
        sys.stdout.write(
            f"{name}: {int(r['commits'])} commits, {r['per_day']} a day, "
            f"longest gap {r['longest_gap_hours']} h; "
            f"ledger {int(r['ledger_lines'])} lines, {r['ledger_per_day']} a day\n"
        )
    return 0


def _events(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """Print every change to a card in the repos' queue history, one event a line (nemik:W744).

    Returns:
        0.

    """
    rows = [event for name in names for event in backfill(name, dirs[name], args.start)]
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=1) + "\n")
        return 0
    for event in rows:
        sys.stdout.write("\t".join(event) + "\n")
    return 0


def _score(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """Print the Brier score per lead of a stored shingle, read against the events (nemik:W759).

    The file holds the tab-separated rows `--forecast` printed; any line that is not a row is
    skipped.

    Returns:
        0.

    """
    rows = shingle_lines(Path(args.score).read_text(encoding="utf-8"))
    events = [e for name in names for e in backfill(name, dirs[name], args.start)]
    got = score_rows(rows, events, datetime.now(UTC).isoformat())
    if args.json:
        sys.stdout.write(json.dumps(got, indent=1) + "\n")
        return 0
    for lead, score in sorted(got.items()):
        sys.stdout.write(f"{lead}\tbrier {score:.3f}\n")
    return 0


def _forecast(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """Print the shingle rows for every open card, issued now, one tab-separated row a line.

    Returns:
        0.

    """
    moment = datetime.now(UTC).isoformat()
    events = [e for name in names for e in backfill(name, dirs[name], args.start)]
    rows = forecast_rows(events, moment)
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=1) + "\n")
        return 0
    for row in rows:
        sys.stdout.write("\t".join(row) + "\n")
    return 0


def _waits(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """Print per repo and status how long finished stints lasted, in days (nemik:W753).

    Returns:
        0.

    """
    rows = {name: waits(backfill(name, dirs[name], args.start)) for name in names}
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=1) + "\n")
        return 0
    for name, by_status in rows.items():
        for status, r in sorted(by_status.items()):
            sys.stdout.write(
                f"{name}\t{status}\tn {int(r['n'])}\tmedian {r['median_days']} d"
                f"\tp90 {r['p90_days']} d\n"
            )
    return 0


def _baseline(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    out: dict[str, dict] = {}
    for name in names:
        repo = dirs[name]
        spec = baseline_spec(repo, args.baseline)
        if spec is None:
            out[name] = {"baseline": None}
            continue
        base, now = queue_at(repo, resolve(repo, spec)), queue_at(repo, "HEAD")
        out[name] = {
            "baseline": spec,
            **variance(base, now),
            "shape": shape_drift(base, now),
        }
    if args.json:
        print(json.dumps(out, indent=1))
        return 0
    for name, v in out.items():
        if v["baseline"] is None:
            print(f"{name}: no baseline (give one, or declare it in {BASELINE_PATH})")
            continue
        added = ", ".join(f"{len(s)} {k}" for k, s in sorted(v["added"].items()))
        print(
            f"{name} since {v['baseline']}: planned {v['planned']}, closed {len(v['closed'])}, "
            f"dropped {len(v['dropped'])}, still open {len(v['still_open'])} "
            f"(done share {v['done_share']}); added since: {added or 'none'}"
        )
        sh = v["shape"]
        print(
            f"  shape: +{sh['edges_added']}/-{sh['edges_removed']} edges, "
            f"{len(sh['retitled'])} planned retitled, {len(sh['rewired'])} re-wired "
            f"(touched share {sh['touched_share']})"
        )
    return 0


def toil(repo: str, ledger: Path) -> list[dict]:
    """nemik:W314: per ISO week, the repo's ledger activity by effort class and the interrupt share.

    Each ledger line is one PROV activity with a start time and an effort class (forecast: a scheduled
    tick or operator-typed work; interrupt: unplanned; unclassified). `toil_share` is interrupt over
    forecast plus interrupt, the tax unplanned work levies on planned work; None when neither occurred.
    """
    from rdflib import RDF
    from rdflib.namespace import PROV

    from nemik.adapter import NEMIK, ledger_graph

    g, _ = ledger_graph(repo, ledger)
    weeks: dict[str, dict[str, int]] = {}
    for act in g.subjects(RDF.type, PROV.Activity):
        stamp = str(g.value(act, PROV.startedAtTime) or "")
        if not stamp:
            continue
        iso = datetime.fromisoformat(stamp).isocalendar()
        cls = str(g.value(act, NEMIK.effortClass) or "unclassified")
        week = weeks.setdefault(f"{iso.year}-W{iso.week:02d}", {})
        week[cls] = week.get(cls, 0) + 1
    rows = []
    for label, counts in sorted(weeks.items()):
        planned = counts.get("forecast", 0)
        unplanned = counts.get("interrupt", 0)
        rows.append(
            {
                "week": label,
                **counts,
                "toil_share": round(unplanned / (planned + unplanned), 3)
                if planned + unplanned
                else None,
            }
        )
    return rows


def _toil(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """`--toil`: the weekly interrupt share per repo, from each repo's ledger."""
    doc = {n: toil(n, dirs[n] / ".claude" / LEDGER) for n in names}
    if args.json:
        print(json.dumps(doc, indent=1))
        return 0
    for name, rows in doc.items():
        print(name)
        for row in rows:
            share = "-" if row["toil_share"] is None else f"{row['toil_share']:.0%}"
            counts = "  ".join(
                f"{k} {v}" for k, v in row.items() if k not in ("week", "toil_share")
            )
            print(f"  {row['week']}  interrupt share {share:>4}  {counts}")
    return 0


def _days(seconds: float) -> str:
    return f"{seconds / 86400:.1f}d"


def _series(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """`--time-in-state` and `--weekly` over the history from `--from` (default: all of it)."""
    for mode, run in (
        ("density", _density),
        ("events", _events),
        ("waits", _waits),
        ("forecast", _forecast),
        ("score", _score),
    ):
        if getattr(args, mode):
            return run(args, names, dirs)
    now = datetime.now(UTC)
    rolled: dict[str, list[dict]] = {}
    spent: dict[str, dict[str, tuple[str, dict[str, float]]]] = {}
    for name in names:
        snaps = snapshots(dirs[name], args.start)
        if args.weekly:
            rolled[name] = weekly(snaps)
            continue
        latest = _status(snaps[-1][1]) if snaps else {}
        by_state = time_in_state(snaps, now)
        spent[name] = {
            s: (latest[s], by_state[s])
            for s in sorted(latest, key=_number)
            if latest[s] not in ("done", "dropped")
        }
    if args.json:
        doc = rolled if args.weekly else spent
        print(json.dumps(doc, indent=1))
        return 0
    for name in names:
        print(name)
        for row in rolled.get(name, []):
            print(
                f"  {row['week']}  opened {row['opened']:3}  closed {row['closed']:3}"
                f"  open {row['open']:3}  blocked {row['blocked_share']:.0%}"
                f"  oldest block {row['oldest_blocked'] or '-'}"
                f" ({row['oldest_blocked_days']}d)"
                f"  operator +{row['operator_asked']}/-{row['operator_answered']}"
                f" open {row['operator_open']} wait {row['operator_wait_days'] or '-'}d"
            )
        for symbol, (state, per) in spent.get(name, {}).items():
            held = "  ".join(f"{k} {_days(v)}" for k, v in per.items())
            print(f"  {symbol} now {state}: {held}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
