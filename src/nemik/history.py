"""nemik:W267: how a workstream's graph changed between two points in its git history.

nemik-history reads each repo's committed `.claude/paths-forward.json` at two revisions (or the
last commit before two dates) and prints what moved: minted, closed, dropped, status flips, edge
changes, and the new blocks on other workstreams. It reads history only, so it works backwards
over everything ever committed; nothing here writes or needs new data.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
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
    args = ap.parse_args(argv)
    dirs = {r: p.parents[1] for r, p in workstream_files(args.root, QUEUE)}
    names = sorted(dirs) if args.all else args.repos
    if not names or args.start is None:
        ap.error("name the repos (or --all) and a --from")
    out: dict[str, Diff] = {}
    for name in names:
        if name not in dirs:
            print(f"ERROR: no workstream {name} under {args.root}", file=sys.stderr)
            return 2
        repo = dirs[name]
        old = queue_at(repo, resolve(repo, args.start))
        new = queue_at(repo, resolve(repo, args.to))
        out[name] = diff(old, new)
    if args.json:
        print(json.dumps({r: asdict(d) for r, d in out.items()}, indent=1))
    else:
        print("\n".join(render(r, d) for r, d in out.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
