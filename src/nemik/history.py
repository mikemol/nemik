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
from itertools import starmap
from pathlib import Path

from nemik.cachestore import user_dir
from nemik.cardevents import Event, events_of
from nemik.check import LEDGER, QUEUE, default_root, workstream_files
from nemik.climate import (
    finish_rates,
    leads_by_repo,
    open_ages,
    open_status,
    waits_of,
)
from nemik.forecastshingle import HORIZONS, issue_blocked, issue_in_line, shingle_rows
from nemik.histdocs import encode, file_name
from nemik.netforecast import replay_row, sweep_alerts, sweep_report, trailing_alerts
from nemik.verify import lead_report, score_shingle, shingle_pairs
from nemik.wake import read_liveness
from nemik.where import matches, parse

RELIABILITY_BINS = 4  # --score cuts each lead's chances into this many bins
# nemik:W966: the status whose cards take no place in a repo's line
BLOCKED = "blocked"


def live_repos(root: Path) -> set[str]:
    """Name the repos with a live session, as nemik-wake reads loop_liveness (nemik:W769).

    A repo whose verdict is anything but "dormant" (ok, or stale: a session that ticked but is
    quiet) has a session to answer; a dormant one, or one with no record, is offline.

    Returns:
        The repo names; empty when no liveness source can be read.

    """
    records, _ = read_liveness(root, None)
    return {repo for repo, rec in records.items() if rec.get("verdict") != "dormant"}


def score_report(
    rows: list[list[str]], done_at: dict[str, str], now: str, grain_days: float
) -> dict[str, dict[str, float]]:
    """Judge stored shingle rows per lead, against persistence and climatology (nemik:W761).

    Returns:
        {lead: lead_report}: n, Brier, the two references' Brier, the skill against each, and the
        reliability bins; only leads the truth's grain allows and whose horizon has passed.

    """
    found = shingle_pairs(rows, done_at, now, grain_days)
    return {lead: lead_report(p, RELIABILITY_BINS) for lead, p in found.items()}


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
    "oldest",
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


def _oldest_first(card: tuple[str, float]) -> float:
    """Sort key for (station, age) pairs: the oldest card first.

    Returns:
        The age, negated.

    """
    return -card[1]


def forecast_rows(events: list[Event], moment: str) -> list[list[str]]:
    """Issue the forecast for every open card at one moment, as shingle rows (nemik:W747).

    Each open card's chances at +1, +3 and +7 days, from the lead times of its repo's cards done by
    then. A card that can start is capped by its place in its repo's line (oldest first, counting
    only the cards that can start) against how many cards the repo finishes a day (nemik:W831); a
    blocked card takes no place in that line and is capped instead by how long blocked stints have
    lasted (nemik:W966). One row per card and lead.

    Returns:
        The rows: issue time, station, lead, age in days, chance.

    """
    leads = leads_by_repo(events, moment)
    rates = finish_rates(events, moment)
    statuses = open_status(events, moment)
    stints = waits_of(events).get(BLOCKED, [])
    ahead: dict[str, int] = {}
    rows: list[list[str]] = []
    for station, age in sorted(open_ages(events, moment).items(), key=_oldest_first):
        repo = station.partition(":")[0]
        place = ahead.get(repo, 0)
        if statuses.get(station) == BLOCKED:
            chances = issue_blocked(leads.get(repo, []), age, HORIZONS, stints)
        else:
            ahead[repo] = place + 1
            chances = issue_in_line(
                leads.get(repo, []), age, HORIZONS, rates.get(repo, 0.0), place
            )
        rows.extend(shingle_rows(moment, station, age, chances))
    return sorted(rows)


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
# nemik:W1127: a time of day names its zone (Z or an offset), or it is read as the machine's local
# time and prints a plausible answer for the wrong instant (luthen's "12:34Z" was 12:34 local)
_ZONED = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})")
# `ago:45m` is the spelling argparse accepts after `--baseline` (a value starting with `-` reads as
# an option there); `-45m` works as `--baseline=-45m`. Bare `45m` would clash with an abbreviated
# sha.
_RELATIVE = re.compile(r"(?:-|ago:)(\d+)([mhd])")
_SECONDS = {"m": 60, "h": 3600, "d": 86400}
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
    committed queue, such as luthen's `R-amtool`) after them by name, never an error.
    """
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


def git_lines(repo: Path, *args: str) -> list[str] | None:
    """Run git in a repo and give its output a line at a time (nemik:W1149).

    Args:
        repo: The repo's directory.
        *args: The git arguments after `-C <repo>`.

    Returns:
        The lines, untouched (a leading space in `git status --porcelain` survives); an empty
        list when git answered with nothing; None when git could not answer.

    """
    out = _git(repo, *args)
    return None if out is None else out.splitlines()


def resolve(repo: Path, spec: str | None) -> str | None:
    """A revision for `spec`: a date means the last commit before it, anything else is a rev.

    None means there is no such point (before the repo's first commit): an empty queue. A time of
    day must name its zone (`Z` or an offset), or be a window back from now such as `-1h`, `-30m`
    or `-2d` (nemik:W1127).

    Raises:
        ValueError: When `spec` is a time of day with no zone.

    """
    if spec is None:
        return "HEAD"
    relative = _RELATIVE.fullmatch(spec)
    if relative or _ZONED.fullmatch(spec):
        # a window back from now, or an instant with its zone: both are an exact point in time
        at = (
            datetime.now(UTC).timestamp()
            - int(relative.group(1)) * _SECONDS[relative.group(2)]
            if relative
            else datetime.fromisoformat(spec.replace(" ", "T")).timestamp()
        )
        if at <= 0:
            # a window longer than the epoch reaches before every commit; git reads no negative time
            return None
        out = _git(repo, "rev-list", "-1", f"--before={int(at)}", "HEAD")
        return (out or "").strip() or None
    if _DATE.fullmatch(spec) and len(spec) > len("YYYY-MM-DD"):
        message = (
            f"{spec} names a time with no zone: write it as {spec}Z (UTC) or with an "
            "offset such as +00:00, or as a window such as -1h"
        )
        raise ValueError(message)
    if _DATE.fullmatch(spec):
        # git reads a bare date as that day at the CURRENT time of day, so "--from 2026-10-11" run
        # in the evening meant the evening of the 11th: pin it to the start of the day (nemik:W318).
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
    (the last one until `now`).
    """
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
        # nemik:W357: operator asks, a card entering or leaving blocked_kind human, counted per
        # week.
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
    declared `.claude/baseline` file (a revision or a date), else None (no baseline declared).
    """
    if spec:
        return spec
    declared = repo / BASELINE_PATH
    if declared.is_file():
        words = declared.read_text(encoding="utf-8").split()
        return words[0] if words else None
    return None


def variance(base: dict, now: dict) -> dict:
    """nemik:W318: planned versus actual since a baseline. The plan is the cards open at the baseline:
    how many are now closed, dropped, or still open. The unplanned is every card minted since, split
    by how it was minted (an interrupt, a tick, or not recorded). Both arguments are parsed queues.
    """
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
    touched either way.
    """
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
    # A blocked_on entry may be a paragraph (an operator ask): the line names it, --json has it
    # whole.
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
        "--oldest",
        type=int,
        metavar="N",
        help="the N oldest open cards of the named repos (--all for the fleet), oldest first: "
        "repo:W<n>, age, status, blockers and title; a ready card is flagged untouched, a blocked "
        "one stuck (W769)",
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
        f"the repo's declared {BASELINE_PATH} (W318). A time names its zone (2026-10-26T14:20Z); "
        "a window back from now is ago:45m, ago:1h or ago:2d, or --baseline=-45m (argparse "
        "reads a bare -45m as an option) (W1127)",
    )
    ap.add_argument(
        "--compact",
        action="store_true",
        help="with --baseline: one fleet line (closed, dropped, added, net) then only the repos "
        f"that changed, at most {ROW_LINES} lines; a queue outside git is read from its card "
        "stamps (W1112)",
    )
    ap.add_argument(
        "--by-cause",
        action="store_true",
        help="with --baseline: the cards added in the window split by caused_by, as children of "
        "an open card, promotions of a done one, outside causes and none, in at most "
        f"{ROW_LINES} lines (W1147)",
    )
    ap.add_argument(
        "--replay",
        default="",
        metavar="AT",
        help="with --baseline=-45m (the window's length): replay the window ending at AT (a zoned "
        "time) from committed history. Prints what was predicted for it from the days before, "
        "what it netted, the shortfall, and an alert when the shortfall passes what the ten "
        "windows before it make normal (W1145)",
    )
    ap.add_argument(
        "--sweep",
        type=int,
        default=0,
        metavar="DAYS",
        help="with --baseline=-45m (the windows' length): judge every window of the last DAYS days "
        "against the ones before it and print 'alerted k of n' with each alerted window's end and "
        "direction (fleet wandering or model wrong); k is a count even when it is zero (W1152)",
    )
    ap.add_argument(
        "--where",
        default="",
        metavar="EXPRESSION",
        help="with --oldest: keep only the cards a find(1)-shaped filter names, then take N. "
        "Predicates field OP value over status, age (30m, 12h, 2d), flag, repo, blocked_on and "
        "title, with = != < > <= >= and ~ (contains); * is any; combine with and, or, not and "
        "parentheses. Example: 'status=ready and not blocked_on=* and age>2d' (W1128)",
    )
    ap.add_argument(
        "--publish",
        type=Path,
        default=None,
        metavar="DIR",
        help="with --waits, --forecast, --score, --events or --density: write the rows to "
        "DIR/<mode>.json as a stamped document the server serves as /history/<mode>.json "
        "(nemik-serve --history-dir DIR), not print them (W854 to W858)",
    )
    ap.add_argument(
        "--append-to",
        metavar="FILE",
        help="with --forecast: append the rows to this shingle file, not print them (W747)",
    )
    args = ap.parse_args(argv, namespace=Opts())
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
        return _baselined(args, names, dirs)
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
        print("\n".join(starmap(render, out.items())))
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


def _density(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
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
    if emit(args, "density", rows):
        return 0
    for name, r in rows.items():
        sys.stdout.write(
            f"{name}: {int(r['commits'])} commits, {r['per_day']} a day, "
            f"longest gap {r['longest_gap_hours']} h; "
            f"ledger {int(r['ledger_lines'])} lines, {r['ledger_per_day']} a day\n"
        )
    return 0


OPEN_AGE_SKIP = frozenset({"done", "dropped"})
# characters of a card's blockers that a text line shows (the JSON keeps all)
WAITS_SHOWN = 50
_CARD_REF = re.compile(r"(?:(?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*):)?W[1-9][0-9]*")
_AGENT_REF = re.compile(r"agent:(?P<repo>[^\s,]+)")
LABEL_SHOWN = 40  # characters of a blocker that is not a card, as a hop's label
# a hop as printed, and the repo whose session it needs ("" for none)
Hop = tuple[str, str]
# repo:W<n> -> (status, blocked_on entries)
Cards = dict[str, tuple[str, list[str]]]


def card_table(docs: dict[str, object]) -> Cards:
    """Index every card of the queues by repo:W<n>, with its status and blockers.

    Returns:
        {repo:W<n>: (status, blocked_on entries as text)}.

    """
    table: Cards = {}
    for repo, doc in docs.items():
        cards = doc.get("waypoints") if isinstance(doc, dict) else None
        for card in cards if isinstance(cards, list) else []:
            if isinstance(card, dict) and card.get("symbol"):
                waits = card.get("blocked_on")
                table[f"{repo}:{card['symbol']}"] = (
                    str(card.get("status", "")),
                    [str(w) for w in waits] if isinstance(waits, list) else [],
                )
    return table


def _hops_for(text: str, repo: str, cards: Cards, trail: frozenset[str]) -> list[Hop]:
    """Give the path that one blocker entry leads down, or none when it has landed.

    Returns:
        The hops; a card on the trail ends it as `(cycle)` and one the queues do not hold as `(?)`.

    """
    head = (text.split(maxsplit=1) or [""])[0]
    if _CARD_REF.fullmatch(head):
        cite = head if ":" in head else f"{repo}:{head}"
        mark = "cycle" if cite in trail else "" if cite in cards else "?"
        if mark:
            return [(f"{cite}({mark})", cite.partition(":")[0])]
        if cards[cite][0] in OPEN_AGE_SKIP:
            return []
        return critical_path(cite, cards, trail)
    agent = _AGENT_REF.match(text)
    if agent:
        return [(f"agent:{agent['repo']}", agent["repo"])]
    if text.startswith("operator"):
        return [("operator", "")]
    return [(text[:LABEL_SHOWN], "")]


def critical_path(
    cite: str, cards: Cards, trail: frozenset[str] = frozenset()
) -> list[Hop]:
    """Give a card's critical path: the longest chain of blockers down to a leaf (nemik:W769).

    Each hop is `repo:W<n>(status)`; the chain ends at a card nothing open blocks (ready or
    working: someone can take it), at `operator`, at an `agent:<repo>` entry, or at a blocker that
    is not a card, as written. A blocker that has landed is not a hop. Ties keep the first.

    Returns:
        The hops, the card first.

    """
    status, waits = cards[cite]
    repo = cite.partition(":")[0]
    best: list[Hop] = []
    for text in waits:
        sub = _hops_for(text, repo, cards, trail | {cite})
        if len(sub) > len(best):
            best = sub
    return [(f"{cite}({status})", repo), *best]


def with_paths(
    rows: list[dict[str, str]], docs: dict[str, object], live: set[str]
) -> list[dict[str, str]]:
    """Add each row's critical path and whether it crosses a repo with no live session.

    Returns:
        The rows with `path` (hops joined by ' -> '), `offline` (the repos with no live session
        the path needs, comma-joined) and `reach` ("OFFLINE-FREE" when none, else the repos).

    """
    cards = card_table(docs)
    out: list[dict[str, str]] = []
    for row in rows:
        hops = critical_path(row["cite"], cards)
        down = sorted({repo for _, repo in hops if repo and repo not in live})
        named = ", ".join(down)
        with_path = dict(row)
        with_path["path"] = " -> ".join(label for label, _ in hops)
        with_path["offline"] = named
        with_path["reach"] = f"crosses offline: {named}" if down else "OFFLINE-FREE"
        out.append(with_path)
    return out


def oldest_cards(
    docs: dict[str, object],
    now: datetime,
    limit: int,
    keep: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    """List the oldest open cards of the queues, oldest first (nemik:W769).

    A card's age runs from its `issued_at`; a card with none, or one that is done or dropped, is
    left out. A ready card is flagged `untouched` (nobody has taken it) and a blocked one `stuck`
    (a chain waiting), since an old ready card and an old blocked card are different problems.

    Args:
        docs: Each repo's parsed queue file, by repo.
        now: The time the ages are taken at.
        limit: How many cards to list.
        keep: A filter parsed by nemik.where (nemik:W1128); only the rows it keeps count toward
            `limit`, so "the 20 oldest that are not blocked" are 20 such cards.

    Returns:
        Up to `limit` rows: cite, age_days, status, flag, blocked_on, title.

    """
    order: list[tuple[datetime, str]] = []
    rows: dict[str, dict[str, str]] = {}
    for repo, doc in docs.items():
        cards = doc.get("waypoints") if isinstance(doc, dict) else None
        for card in cards if isinstance(cards, list) else []:
            if not isinstance(card, dict):
                continue
            status, symbol = str(card.get("status", "")), str(card.get("symbol", ""))
            try:
                born = datetime.fromisoformat(str(card.get("issued_at", "")))
            except ValueError:
                continue
            if status in OPEN_AGE_SKIP or not symbol:
                continue
            waits = card.get("blocked_on")
            row = {
                "cite": f"{repo}:{symbol}",
                "age_days": f"{(now - born).total_seconds() / 86400:.1f}",
                "status": status,
                "flag": {"ready": "untouched", "blocked": "stuck"}.get(status, ""),
                "blocked_on": ", ".join(str(w) for w in waits)
                if isinstance(waits, list)
                else "",
                "title": str(card.get("title", "")),
            }
            if keep and not matches(list(keep), row):
                continue
            order.append((born, row["cite"]))
            rows[row["cite"]] = row
    order.sort()
    return [rows[cite] for _, cite in order[:limit]]


def oldest_rows(
    files: dict[str, Path], root: Path, limit: int, keep: tuple[str, ...] = ()
) -> list[dict[str, str]]:
    """Read the queues and list the oldest open cards with their paths (nemik:W853).

    The one function the CLI's --oldest and the server's /oldest.json both call. It reads files
    and spawns nothing.

    Args:
        files: Each repo's name and its queue file's path; an unreadable one is left out.
        root: The fleet root, where the liveness record is read.
        limit: How many cards to list.
        keep: A parsed nemik.where filter; only the rows it keeps are listed (nemik:W1128).

    Returns:
        Up to `limit` rows: cite, age_days, status, flag, blocked_on, title, path, offline, reach.

    """
    docs: dict[str, object] = {}
    for name, path in files.items():
        try:
            docs[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    rows = oldest_cards(docs, datetime.now(UTC), limit, keep)
    return with_paths(rows, docs, live_repos(root))


def _oldest(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """Print the N oldest open cards of the named repos, one a line (nemik:W769).

    With --where EXPRESSION only the cards it keeps count, so `--oldest 20 --where 'not
    blocked_on=*'` lists the 20 oldest cards that wait on nothing (nemik:W1128).

    Returns:
        0; 2 when the --where expression is not well formed, the error on stderr.

    """
    try:
        keep = tuple(parse(args.where))
    except ValueError as error:
        sys.stderr.write(f"nemik-history: --where: {error}\n")
        return 2
    rows = oldest_rows(
        {name: dirs[name] / QUEUE_PATH for name in names}, args.root, args.oldest, keep
    )
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=1) + "\n")
        return 0
    for r in rows:
        held = r["blocked_on"]
        cut = "..." if len(held) > WAITS_SHOWN else ""
        waits = f"  blocked on {held[:WAITS_SHOWN]}{cut}" if held else ""
        flag = f" [{r['flag']}]" if r["flag"] else ""
        sys.stdout.write(
            f"{r['cite']:24} {r['age_days']:>6} d  {r['status']}{flag}{waits}  {r['title']}\n"
        )
        sys.stdout.write(f"    path: {r['path']}  [{r['reach']}]\n")
    return 0


def _events(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """Print every change to a card in the repos' queue history, one event a line (nemik:W744).

    Returns:
        0.

    """
    rows = [event for name in names for event in backfill(name, dirs[name], args.start)]
    if emit(args, "events", rows):
        return 0
    for event in rows:
        sys.stdout.write("\t".join(event) + "\n")
    return 0


def _auc_text(value: float) -> str:
    """Word a discrimination score (nemik:W965).

    Returns:
        The score to two places, or n/a when no card finished or every one did (it is negative).

    """
    return "n/a" if value < 0 else f"{value:.2f}"


def _score(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """Judge a stored shingle per lead, read against the events (nemik:W759, W761).

    The file holds the tab-separated rows `--forecast` printed; any line that is not a row is
    skipped. Per lead: the count, the Brier score, the two references' Brier (nothing changes; the
    base rate) with the skill against each, and the reliability bins.

    Returns:
        0.

    """
    rows = shingle_lines(Path(args.score).read_text(encoding="utf-8"))
    events = [e for name in names for e in backfill(name, dirs[name], args.start)]
    got = score_report(
        rows, first_done(events), datetime.now(UTC).isoformat(), COMMIT_GRAIN_DAYS
    )
    if emit(args, "score", got):
        return 0
    for lead, r in sorted(got.items()):
        sys.stdout.write(
            f"{lead}\tn {int(r['n'])}\tbrier {r['brier']:.3f}"
            f"\tpersistence {r['persistence']:.3f} (skill {r['skill_persistence']:.2f})"
            f"\tclimatology {r['climatology']:.3f} (skill {r['skill_climatology']:.2f})"
            f"\tdiscrimination {_auc_text(r['discrimination'])}\n"
        )
        for k in range(RELIABILITY_BINS):
            if f"bin{k}_n" in r:
                sys.stdout.write(
                    f"\t  said {r[f'bin{k}_chance']:.2f}: {r[f'bin{k}_share']:.2f} happened"
                    f" (n {int(r[f'bin{k}_n'])})\n"
                )
    return 0


def _forecast(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """Print the shingle rows for every open card, issued now, one tab-separated row a line.

    Returns:
        0.

    """
    moment = datetime.now(UTC).isoformat()
    events = [e for name in names for e in backfill(name, dirs[name], args.start)]
    rows = forecast_rows(events, moment)
    if args.append_to:
        # the shingle is append-only: every issue is kept with its lead, none rewritten
        with Path(args.append_to).open("a", encoding="utf-8") as shingle:
            shingle.writelines("\t".join(row) + "\n" for row in rows)
        sys.stdout.write(f"appended {len(rows)} rows to {args.append_to}\n")
        return 0
    if emit(args, "forecast", rows):
        return 0
    for row in rows:
        sys.stdout.write("\t".join(row) + "\n")
    return 0


class Opts(argparse.Namespace):
    """The options the modes that publish read, typed so reading them adds no Any (nemik:W854)."""

    json: bool
    publish: Path | None
    where: str
    oldest: int
    root: Path
    baseline: str | None
    compact: bool
    by_cause: bool
    replay: str
    sweep: int


def emit(args: Opts, mode: str, rows: object) -> bool:
    """Publish a mode's JSON rows as a stamped document, or print them, when asked (nemik:W854).

    With --publish DIR the rows go to DIR/<mode>.json as a histdocs document, the file the
    server's /history/<mode>.json route serves; the write goes to a sibling file and is renamed
    into place, so a reader never sees half a document. With --json they print.

    Args:
        args: The parsed options.
        mode: The history mode, one of histdocs.MODES.
        rows: What the mode computed.

    Returns:
        True when it published or printed (the caller returns 0), False when the caller prints
        the text form.

    """
    if args.publish is not None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        args.publish.mkdir(parents=True, exist_ok=True)
        path = args.publish / file_name(mode)
        partial = path.with_name(f".{path.name}.part")
        partial.write_text(encode(stamp, json.dumps(rows, indent=1)), encoding="utf-8")
        partial.replace(path)
        return True
    if args.json:
        sys.stdout.write(json.dumps(rows, indent=1) + "\n")
        return True
    return False


def _waits(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """Print per repo and status how long finished stints lasted, in days (nemik:W753).

    Returns:
        0.

    """
    rows = {name: waits(backfill(name, dirs[name], args.start)) for name in names}
    if emit(args, "waits", rows):
        return 0
    for name, by_status in rows.items():
        for status, r in sorted(by_status.items()):
            sys.stdout.write(
                f"{name}\t{status}\tn {int(r['n'])}\tmedian {r['median_days']} d"
                f"\tp90 {r['p90_days']} d\n"
            )
    return 0


ROW_LINES = 10  # nemik:W1112: the most lines a hook may print, the host's tick-open cap


def window_start(spec: str) -> datetime | None:
    """Name the instant a window spec reaches back to, for a queue with no git history.

    Args:
        spec: A window back from now (`-45m`, `ago:2d`) or an instant with its zone.

    Returns:
        The instant, or None when `spec` is a revision or a bare date (only git reads those).

    """
    relative = _RELATIVE.fullmatch(spec)
    if relative:
        back = int(relative.group(1)) * _SECONDS[relative.group(2)]
        return datetime.fromtimestamp(datetime.now(UTC).timestamp() - back, UTC)
    if _ZONED.fullmatch(spec):
        return datetime.fromisoformat(spec.replace(" ", "T"))
    return None


def _stamp(value: object) -> datetime | None:
    """Read a queue timestamp.

    Returns:
        The instant, zoned (a bare one is read as UTC); None when absent or unreadable.

    """
    if not isinstance(value, str) or not value:
        return None
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


# closed, dropped, added and still open: what a window did to one queue
Counts = tuple[int, int, int, int]


def stamp_counts(doc: QueueDoc, since: datetime) -> Counts:
    """Count a queue's window from its card stamps alone (nemik:W1112).

    The host's queue is not under git, so its past cannot be read back. Its cards carry when they
    were issued, completed and dropped, which is enough: a card issued since is added, one finished
    before the window is neither planned nor counted, one finished since is closed, and a residue
    entry dropped since is dropped.

    Args:
        doc: The queue document as it stands now.
        since: The window's start.

    Returns:
        (closed, dropped, added, still open) where still open is the planned cards not yet done.

    """
    closed = added = still_open = 0
    for card in doc.get("waypoints", []):
        issued, done = _stamp(card.get("issued_at")), _stamp(card.get("completed"))
        finished = card.get("status") == "done"
        if issued is not None and issued >= since:
            added += 1
        elif finished and done is not None and done >= since:
            closed += 1
        elif not finished:
            still_open += 1
    dropped = sum(
        1
        for entry in doc.get("residue", [])
        if (at := _stamp(entry.get("dropped_at"))) is not None and at >= since
    )
    return closed, dropped, added, still_open


def _issued_since(card: Waypoint, since: datetime | None) -> bool:
    """Say whether a card arrived in the window, by its issued_at stamp (nemik:W1112).

    A symbol new against the baseline is not yet an add: a queue left uncommitted for a month
    shows all of that month's cards as new against its last commit, and arrival is when a card
    was issued, the clock nemik-pacing and the ruling both use.

    Returns:
        True when there is no window, no stamp, or the stamp is at or after the window's start.

    """
    if since is None:
        return True
    issued = _stamp(card.get("issued_at"))
    return issued is None or issued >= since


def burn_counts(base: QueueDoc, now: QueueDoc, since: datetime | None = None) -> Counts:
    """Count a queue's window from two copies of it, as `variance` does (nemik:W1112).

    Args:
        base: The queue at the window's start.
        now: The queue now.
        since: The window's start when it is a time; a card new against `base` but issued before
            it is not counted as added.

    Returns:
        (closed, dropped, added, still open): the plan is the cards open at `base`. A card added
        and dropped inside the window is in the residue with no stamp and counts as added.

    """
    gone_then, gone_now = _dropped(base), _dropped(now)
    then, after = _status(base), _status(now)
    planned = {
        s
        for s, st in then.items()
        if st not in {"done", "dropped"} and s not in gone_then
    }
    closed = sum(1 for s in planned if after.get(s) == "done")
    dropped = sum(1 for s in planned if s in gone_now)
    still = sum(
        1 for s in planned if s not in gone_now and after.get(s) not in {None, "done"}
    )
    known = set(then) | gone_then
    old = {
        str(card["symbol"])
        for card in now.get("waypoints", [])
        if not _issued_since(card, since)
    }
    added = sum(1 for s in set(after) | gone_now if s not in known and s not in old)
    return closed, dropped, added, still


def _busiest(pair: tuple[str, Counts]) -> tuple[int, str]:
    """Order repos by how much changed, most first, then by name.

    Returns:
        The sort key.

    """
    name, (closed, dropped, added, _) = pair
    return -(closed + dropped + added), name


def fleet_row(
    rows: dict[str, Counts],
    spec: str,
    limit: int = ROW_LINES,
    births: dict[str, int] | None = None,
) -> list[str]:
    """Fold a fleet's windows into one total line and the repos that changed (nemik:W1112).

    Args:
        rows: Each repo's counts.
        spec: The window as the operator wrote it, for the first line.
        limit: The most lines to give.
        births: Each repo whose queue file was created inside the window, with its card count.
            Its cards are not work added to a plan that existed, so they stay out of every total.

    Returns:
        The fleet's closed, dropped and added with their net (closed plus dropped less added, so a
        positive net is a burn-down), the cards born with new queues, then one line per repo that
        changed, busiest first, then one per new queue; a tail line counts the repos that did not
        fit. At most `limit` lines.

    """
    born = births or {}
    closed, dropped, added, still = (sum(c[i] for c in rows.values()) for i in range(4))
    head = (
        f"fleet since {spec}: closed {closed}, dropped {dropped}, added {added}, "
        f"net {closed + dropped - added:+d}, open (planned) {still}, {len(rows)} repos"
    )
    if born:
        head += f"; {sum(born.values())} cards born in {len(born)} new queues"
    changed = sorted(
        ((name, c) for name, c in rows.items() if c[0] + c[1] + c[2]),
        key=_busiest,
    )
    entries = [
        f"{name}: closed {c}, dropped {d}, added {a}, net {c + d - a:+d}"
        for name, (c, d, a, _) in changed
    ]
    entries += [f"{name}: born, {born[name]} cards" for name in sorted(born)]
    room = limit - 1
    shown = entries if len(entries) <= room else entries[: room - 1]
    lines = [head, *shown]
    if len(shown) < len(entries):
        lines.append(f"+{len(entries) - len(shown)} more repos changed")
    return lines


def born_cards(adds: str, since: datetime, doc: QueueDoc) -> int:
    """Count a queue's cards when the file was created inside the window (nemik:W1112).

    Args:
        adds: The commit times (ISO, newest first) at which the queue file was added.
        since: The window's start.
        doc: The queue as it stands now.

    Returns:
        The card count when the oldest add is at or after `since`, else 0.

    """
    stamps = adds.split()
    first = _stamp(stamps[-1]) if stamps else None
    if first is None or first < since:
        return 0
    return len(doc.get("waypoints", []))


def born_in(repo: Path, spec: str) -> int:
    """Count the cards of a queue file that was created inside the window (nemik:W1112).

    Args:
        repo: The repo's directory.
        spec: The window (`-1d`, `ago:45m` or a zoned instant).

    Returns:
        The queue's card count when its first commit lies in the window, else 0: a revision or a
        bare date names no instant to compare with, and a queue outside git has no first commit.

    """
    since = window_start(spec)
    if since is None:
        return 0
    adds = _git(repo, "log", "--diff-filter=A", "--format=%cI", "--", QUEUE_PATH)
    return born_cards(adds or "", since, queue_at(repo, "HEAD"))


def live_queue(repo: Path, committed: QueueDoc) -> QueueDoc:
    """Read a queue as it stands on disk, so a card minted after the last commit counts (W1112).

    A queue reaches git only when the stack carrying it lands, a gate of half an hour, and a window
    that read HEAD saw no adds in that time while a longer one rose when the commits arrived.

    Args:
        repo: The repo's directory.
        committed: The queue as committed, for a repo with no file on disk or an unreadable one.

    Returns:
        The queue file's content now; `committed` when there is no readable file.

    """
    path = repo / QUEUE_PATH
    if not path.is_file():
        return committed
    try:
        return queue_at(repo, "HEAD", known=path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return committed


# adds that are children of an open card, promotions of a done card, of an outside cause, of none
Causes = tuple[int, int, int, int]
_OWN_CARD = re.compile(r"W[1-9][0-9]*")


def _cause_of(card: Waypoint, status: dict[str, str]) -> int:
    """Say where one added card came from (nemik:W1147).

    Args:
        card: The added waypoint.
        status: Each of this queue's cards' status now.

    Returns:
        0 for a child of a card still open (an atomization), 1 for a promotion (the card it is
        caused by is done or gone: a finished card is never reopened, its class is minted
        beside it), 2 for a cause outside this queue (another repo's card, a peer, the operator,
        a letter), 3 for no cause stated.

    """
    cause = card.get("caused_by")
    if not isinstance(cause, str) or not cause:
        return 3
    if not _OWN_CARD.fullmatch(cause):
        return 2
    return 0 if status.get(cause) not in {None, "done"} else 1


def cause_counts(
    base: QueueDoc, now: QueueDoc, since: datetime | None = None
) -> Causes:
    """Split the cards added between two copies of a queue by what caused them (nemik:W1147).

    Args:
        base: The queue at the window's start.
        now: The queue now.
        since: The window's start when it is a time; a card new against `base` but issued before
            it is not an add, as in burn_counts.

    Returns:
        (children, promotions, outside, none) over the cards `now` holds that `base` did not know
        and that arrived in the window. A card added and dropped inside it sits in the residue,
        which keeps no cause, so it counts under none: the total equals burn_counts' added.

    """
    known = set(_status(base)) | _dropped(base)
    status = _status(now)
    tally = [0, 0, 0, 0]
    for card in now.get("waypoints", []):
        if str(card["symbol"]) not in known and _issued_since(card, since):
            tally[_cause_of(card, status)] += 1
    tally[3] += sum(1 for s in _dropped(now) if s not in known and s not in status)
    return tally[0], tally[1], tally[2], tally[3]


def stamp_causes(doc: QueueDoc, since: datetime) -> Causes:
    """Split the cards issued since an instant by what caused them, from the stamps alone.

    Returns:
        (children, promotions, outside, none), for a queue outside git that has no past to diff.

    """
    status = _status(doc)
    tally = [0, 0, 0, 0]
    for card in doc.get("waypoints", []):
        issued = _stamp(card.get("issued_at"))
        if issued is not None and issued >= since:
            tally[_cause_of(card, status)] += 1
    return tally[0], tally[1], tally[2], tally[3]


def _most_added(pair: tuple[str, Causes]) -> tuple[int, str]:
    """Order repos by how many cards they added, most first, then by name.

    Returns:
        The sort key.

    """
    return -sum(pair[1]), pair[0]


def cause_row(rows: dict[str, Causes], spec: str, limit: int = ROW_LINES) -> list[str]:
    """Fold a fleet's adds into one total line and the repos that added, by cause (nemik:W1147).

    Args:
        rows: Each repo's split.
        spec: The window as the operator wrote it.
        limit: The most lines to give.

    Returns:
        The fleet's adds as child, promoted, outside and none, then one line per repo that added,
        most first, with a tail line for the ones that did not fit. At most `limit` lines.

    """
    total = [sum(c[i] for c in rows.values()) for i in range(4)]
    head = (
        f"fleet since {spec}: added {sum(total)}: child {total[0]}, promoted {total[1]}, "
        f"outside {total[2]}, none {total[3]}"
    )
    adders = sorted(
        ((name, c) for name, c in rows.items() if sum(c)),
        key=_most_added,
    )
    entries = [
        f"{name}: added {sum(c)}: child {c[0]}, promoted {c[1]}, outside {c[2]}, none {c[3]}"
        for name, c in adders
    ]
    room = limit - 1
    shown = entries if len(entries) <= room else entries[: room - 1]
    lines = [head, *shown]
    if len(shown) < len(entries):
        lines.append(f"+{len(entries) - len(shown)} more repos added")
    return lines


def _causes_for(repo: Path, spec: str) -> Causes | None:
    """Split one repo's adds in the window: from its commits, or from its stamps outside git.

    Returns:
        The split; None when the repo has no queue to read.

    """
    now = queue_at(repo, "HEAD")
    since = window_start(spec)
    if since is not None and not now:
        path = repo / QUEUE_PATH
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        return stamp_causes(queue_at(repo, "HEAD", known=text), since)
    base = queue_at(repo, resolve(repo, spec))
    return cause_counts(base, live_queue(repo, now), since)


def _counts_for(repo: Path, spec: str) -> Counts | None:
    """Count one repo's window: from its commits, or from its card stamps outside git.

    Returns:
        The counts; None when the repo has no queue to read. A `spec` that is a time of day with no
        zone is refused by `resolve`, as everywhere.

    """
    now = queue_at(repo, "HEAD")
    since = window_start(spec)
    if since is not None and not now:
        # a queue outside git (the host's) is read from its card stamps
        path = repo / QUEUE_PATH
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        return stamp_counts(queue_at(repo, "HEAD", known=text), since)
    base = queue_at(repo, resolve(repo, spec))
    return burn_counts(base, live_queue(repo, now), since)


# the days before the earliest past window that a replayed prediction is made from
REPLAY_DAYS = 7
# the earlier windows a replayed alert's baseline is learned from
REPLAY_WINDOWS = 10


def window_minutes(spec: str) -> int:
    """Read a window written back from now (`-45m`, `ago:2h`) as minutes.

    Returns:
        Its length in minutes.

    Raises:
        ValueError: When `spec` is not such a window.

    """
    relative = _RELATIVE.fullmatch(spec)
    if relative is None:
        message = f"{spec} is not a window such as -45m or ago:2h"
        raise ValueError(message)
    return int(relative.group(1)) * _SECONDS[relative.group(2)] // 60


def _net_between(
    names: list[str], dirs: dict[str, Path], start: datetime, end: datetime
) -> int:
    """Count the fleet's net over a past window from the queues as committed then (W1145).

    Returns:
        Closed plus dropped less added, summed over the repos.

    """
    total = 0
    for name in names:
        repo = dirs[name]
        stamp = "%Y-%m-%dT%H:%M:%SZ"
        base = queue_at(repo, resolve(repo, start.astimezone(UTC).strftime(stamp)))
        now = queue_at(repo, resolve(repo, end.astimezone(UTC).strftime(stamp)))
        closed, dropped, added, _ = burn_counts(base, now, start)
        total += closed + dropped - added
    return total


def _series_nets(
    names: list[str], dirs: dict[str, Path], edges: list[datetime]
) -> list[int]:
    """Count the fleet's net over each window between consecutive instants (nemik:W1152).

    Each repo's queue is read once per distinct revision across the instants, so a long run of
    windows costs the commits that fell in it and not one read per window.

    Returns:
        Closed plus dropped less added over each window, summed over the repos, oldest first.

    """
    nets = [0] * (len(edges) - 1)
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    for name in names:
        repo = dirs[name]
        docs: list[QueueDoc] = []
        last_rev: str | None = None
        for at, edge in enumerate(edges):
            rev = resolve(repo, edge.astimezone(UTC).strftime(stamp))
            if at == 0 or rev != last_rev:
                last_rev = rev
                docs.append(queue_at(repo, rev))
            else:
                docs.append(docs[-1])
        for at in range(len(nets)):
            if docs[at] is docs[at + 1]:
                continue
            closed, dropped, added, _ = burn_counts(docs[at], docs[at + 1], edges[at])
            nets[at] += closed + dropped - added
    return nets


def _daily_before(names: list[str], dirs: dict[str, Path], at: datetime) -> list[int]:
    """Count the fleet's net over each of the REPLAY_DAYS days before an instant (W1153).

    Returns:
        The daily nets, oldest first.

    """
    edges = [
        datetime.fromtimestamp(at.timestamp() - 86400 * d, UTC)
        for d in range(REPLAY_DAYS, -1, -1)
    ]
    return _series_nets(names, dirs, edges)


def _ends(
    edges: list[datetime], skip: int, alerts: list[tuple[int, str]]
) -> list[tuple[str, str]]:
    """Label each alerted window with the time it ends (W1152).

    Args:
        edges: The instants between the windows.
        skip: How many windows of the series the alerts' indices leave out.
        alerts: Each alerted window's index and direction.

    Returns:
        (end time, direction) for each.

    """
    stamp = "%Y-%m-%dT%H:%MZ"
    return [(edges[skip + at + 1].strftime(stamp), way) for at, way in alerts]


def sweep_text(
    window: str, days: int, names: list[str], dirs: dict[str, Path], end: datetime
) -> list[str]:
    """Sweep the windows of the last `days` days, each judged by the ones before it (W1152).

    Judged twice, side by side (W1153). The fixed prediction is the mean daily net of the
    REPLAY_DAYS before the first window; the trailing one is the mean net of the REPLAY_DAYS of
    windows just before each window. Neither looks ahead; each window's baseline is learned from
    the REPLAY_WINDOWS windows before it. The alerts are reported as a count of the windows
    judged, zero included, each with its end time and direction. Only committed history is swept.

    Args:
        window: The windows' length written back from now (`-45m`).
        days: How many days to sweep.
        names: The repos to count.
        dirs: Each repo's directory.
        end: Where the last window ends.

    Returns:
        The count line and the alerted windows, at most ROW_LINES lines. A `window` that is not a
        window, or a history too short to predict from, raises ValueError.

    """
    minutes = window_minutes(window)
    span = REPLAY_DAYS * 24 * 60 // minutes
    edges = [
        datetime.fromtimestamp(end.timestamp() - minutes * 60 * k, UTC)
        for k in range(days * 24 * 60 // minutes + REPLAY_WINDOWS + span, -1, -1)
    ]
    nets = _series_nets(names, dirs, edges)
    daily = _daily_before(names, dirs, edges[span])
    fixed = sweep_alerts(daily, minutes, nets[span:], REPLAY_WINDOWS)
    trailing = trailing_alerts(nets, span, REPLAY_WINDOWS)
    swept = f"{minutes} minutes over {days} days"
    half = ROW_LINES // 2
    return [
        *sweep_report(
            fixed[0], _ends(edges, span, fixed[1]), swept, half, "fixed prediction: "
        ),
        *sweep_report(
            trailing[0],
            _ends(edges, 0, trailing[1]),
            swept,
            half,
            "trailing prediction: ",
        ),
    ]


def _sweep(window: str, days: int, names: list[str], dirs: dict[str, Path]) -> int:
    """Print a sweep over the last `days` days (W1152).

    Returns:
        0; 2 with the reason on stderr when it cannot be swept.

    """
    try:
        lines = sweep_text(window, days, names, dirs, datetime.now(UTC))
    except ValueError as error:
        sys.stderr.write(f"nemik-history: --sweep: {error}\n")
        return 2
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def replay_text(
    window: str, at_spec: str, names: list[str], dirs: dict[str, Path]
) -> str:
    """Replay a past window: what was predicted for it, what happened, and any alert (W1145).

    The prediction is the mean daily net of the REPLAY_DAYS before the earliest of the
    REPLAY_WINDOWS earlier windows, so it looks ahead of none; the baseline is those windows'
    own shortfalls. Only committed history is replayed: a card that was never committed
    cannot be seen at a past instant.

    Args:
        window: The window's length written back from now (`-45m`).
        at_spec: The instant the window ends, with its zone.
        names: The repos to count.
        dirs: Each repo's directory.

    Returns:
        The replay line, and the alert beneath it when there is one.

    Raises:
        ValueError: When `window` is not a window, `at_spec` names no zone, or the history is
            too short to predict or to learn a baseline.

    """
    minutes = window_minutes(window)
    if not _ZONED.fullmatch(at_spec):
        message = f"{at_spec} names no zone: write it as 2026-10-27T03:13:00Z"
        raise ValueError(message)
    end = datetime.fromisoformat(at_spec.replace(" ", "T"))
    step = minutes * 60
    edges = [
        datetime.fromtimestamp(end.timestamp() - step * k, UTC)
        for k in range(REPLAY_WINDOWS + 2)
    ]
    realized = _net_between(names, dirs, edges[1], edges[0])
    past = [
        _net_between(names, dirs, edges[k + 1], edges[k])
        for k in range(1, REPLAY_WINDOWS + 1)
    ]
    first = edges[-1].timestamp()
    daily = [
        _net_between(
            names,
            dirs,
            datetime.fromtimestamp(first - 86400 * (d + 1), UTC),
            datetime.fromtimestamp(first - 86400 * d, UTC),
        )
        for d in range(REPLAY_DAYS)
    ]
    return replay_row(daily, minutes, past, realized)


def _replay(window: str, at_spec: str, names: list[str], dirs: dict[str, Path]) -> int:
    """Print a replayed window (W1145).

    Returns:
        0; 2 with the reason on stderr when it cannot be replayed.

    """
    try:
        text = replay_text(window, at_spec, names, dirs)
    except ValueError as error:
        sys.stderr.write(f"nemik-history: --replay: {error}\n")
        return 2
    sys.stdout.write(text + "\n")
    return 0


def _by_cause(baseline: str, names: list[str], dirs: dict[str, Path]) -> int:
    """Print the fleet's adds split by what caused them, in at most ROW_LINES lines (W1147).

    A queue created inside the window is born and not counted, as in the compact row.

    Returns:
        0; 2 when a baseline is a time of day with no zone.

    """
    rows: dict[str, Causes] = {}
    for name in names:
        spec = baseline_spec(dirs[name], baseline)
        if spec is None:
            continue
        try:
            split = None if born_in(dirs[name], spec) else _causes_for(dirs[name], spec)
        except ValueError as error:
            sys.stderr.write(f"{name}: {error}\n")
            return 2
        if split is not None:
            rows[name] = split
    sys.stdout.write("\n".join(cause_row(rows, baseline or "declared")) + "\n")
    return 0


def _baselined(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """Run `--baseline` in its full report, as the compact fleet row, or split by cause.

    Returns:
        The mode's exit status.

    """
    if args.sweep and args.baseline:
        return _sweep(args.baseline, args.sweep, names, dirs)
    if args.replay and args.baseline:
        return _replay(args.baseline, args.replay, names, dirs)
    if args.by_cause and args.baseline is not None:
        return _by_cause(args.baseline, names, dirs)
    if args.compact and args.baseline is not None:
        return _compact(args.baseline, names, dirs)
    return _baseline(args, names, dirs)


def _compact(baseline: str, names: list[str], dirs: dict[str, Path]) -> int:
    """Print the fleet's burndown in at most ROW_LINES lines (nemik:W1112).

    Returns:
        0; 2 when a baseline is a time of day with no zone.

    """
    rows: dict[str, Counts] = {}
    births: dict[str, int] = {}
    for name in names:
        spec = baseline_spec(dirs[name], baseline)
        if spec is None:
            continue
        try:
            born = born_in(dirs[name], spec)
            counts = None if born else _counts_for(dirs[name], spec)
        except ValueError as error:
            sys.stderr.write(f"{name}: {error}\n")
            return 2
        if born:
            births[name] = born
        elif counts is not None:
            rows[name] = counts
    sys.stdout.write(
        "\n".join(fleet_row(rows, baseline or "declared", births=births)) + "\n"
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
        try:
            start = resolve(repo, spec)
        except ValueError as error:
            sys.stderr.write(f"{name}: {error}\n")
            return 2
        base, now = queue_at(repo, start), queue_at(repo, "HEAD")
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

    Each ledger line is one PROV activity with a start time and an effort class (forecast: a
    scheduled tick or operator-typed work; interrupt: unplanned; unclassified). `toil_share` is
    interrupt over forecast plus interrupt, the tax unplanned work levies on planned work; None when
    neither occurred.
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
        row: dict[str, object] = {"week": label}
        row.update(counts)
        row["toil_share"] = (
            round(unplanned / (planned + unplanned), 3) if planned + unplanned else None
        )
        rows.append(row)
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


def _series(args: Opts, names: list[str], dirs: dict[str, Path]) -> int:
    """`--time-in-state` and `--weekly` over the history from `--from` (default: all of it)."""
    for mode, run in (
        ("density", _density),
        ("events", _events),
        ("waits", _waits),
        ("forecast", _forecast),
        ("score", _score),
        ("oldest", _oldest),
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
