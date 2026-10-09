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
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from nemik.check import QUEUE, default_root, workstream_files

QUEUE_PATH = f".claude/{QUEUE}"
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")
_CROSS = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*):W[1-9][0-9]*")


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


def _status(queue: dict) -> dict[str, str]:
    return {w["symbol"]: w.get("status", "") for w in queue.get("waypoints", [])}


def _dropped(queue: dict) -> set[str]:
    return {r["symbol"] for r in queue.get("residue", [])}


def _edges(queue: dict) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for w in queue.get("waypoints", []):
        sym = w["symbol"]
        out |= {("enables", sym, t) for t in w.get("enables", [])}
        out |= {("waits", sym, b) for b in w.get("blocked_on", [])}
    return out


def _number(symbol: str) -> int:
    return int(symbol.lstrip("W") or 0)


def diff(old: dict, new: dict) -> Diff:
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


def _git(repo: Path, *args: str) -> str | None:
    run = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return run.stdout if run.returncode == 0 else None


def resolve(repo: Path, spec: str | None) -> str | None:
    """A revision for `spec`: a date means the last commit before it, anything else is a rev.

    None means there is no such point (before the repo's first commit): an empty queue.
    """
    if spec is None:
        return "HEAD"
    if _DATE.fullmatch(spec):
        out = _git(repo, "rev-list", "-1", f"--before={spec}", "HEAD")
        return (out or "").strip() or None
    return spec


def queue_at(repo: Path, rev: str | None) -> dict:
    """The parsed queue as committed at `rev`; empty when there is none then."""
    if rev is None:
        return {}
    text = _git(repo, "show", f"{rev}:{QUEUE_PATH}")
    return json.loads(text) if text else {}


Snapshot = tuple[datetime, dict]


def snapshots(repo: Path, since: str | None = None) -> list[Snapshot]:
    """Every committed state of the queue, oldest first, as (commit time, parsed queue).

    `since` is a revision or date (see `resolve`): only commits after it. One `git show` per commit
    that touched the file, so a long history costs that many reads.
    """
    start = resolve(repo, since) if since else None
    span = f"{start}..HEAD" if start else "HEAD"
    log = _git(repo, "log", "--format=%H%x09%cI", "--reverse", span, "--", QUEUE_PATH)
    out: list[Snapshot] = []
    for line in (log or "").splitlines():
        sha, _, stamp = line.partition("\t")
        queue = queue_at(repo, sha)
        if queue:
            out.append((datetime.fromisoformat(stamp), queue))
    return out


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
    for (year, week), inside in sorted(weeks.items()):
        for at, queue in inside:
            for symbol, status in _status(queue).items():
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
                "open": len(open_cards),
                "blocked_share": round(len(blocked) / len(open_cards), 3)
                if open_cards
                else 0.0,
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
    args = ap.parse_args(argv)
    dirs = {r: p.parents[1] for r, p in workstream_files(args.root, QUEUE)}
    names = sorted(dirs) if args.all else args.repos
    if not names or (args.start is None and not (args.time_in_state or args.weekly)):
        ap.error("name the repos (or --all) and a --from")
    for name in names:
        if name not in dirs:
            print(f"ERROR: no workstream {name} under {args.root}", file=sys.stderr)
            return 2
    if args.time_in_state or args.weekly:
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


def _days(seconds: float) -> str:
    return f"{seconds / 86400:.1f}d"


def _series(args: argparse.Namespace, names: list[str], dirs: dict[str, Path]) -> int:
    """`--time-in-state` and `--weekly` over the history from `--from` (default: all of it)."""
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
            )
        for symbol, (state, per) in spent.get(name, {}).items():
            held = "  ".join(f"{k} {_days(v)}" for k, v in per.items())
            print(f"  {symbol} now {state}: {held}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
