# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W330, W1006: nemik-work W<n>: mark W<n> working.

There is no limit on working cards (operator 2026-10-15, host 695f3e0a line 68086: requiring the
count to be one "is fragile and puts backpressure in some of the wrong places"). nemik-check warns
on none working while cards are ready, and the pre-commit hook refuses a code commit with none.
This marks W<n> working, clears its landed blockers, and demotes no other card, all through the one
writer, mikemol-paths-forward. It never edits the queue file itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from nemik.tomlview import strings, table, tables


def working(state: Path) -> list[str]:
    """Give the symbols of the cards currently working, read from the queue file.

    Returns:
        The symbols of the working cards.

    """
    data = table(json.loads(state.read_text(encoding="utf-8")))
    return [
        str(w["symbol"])
        for w in tables(data.get("waypoints"))
        if w.get("status") == "working"
    ]


def blockers(state: Path, symbol: str) -> tuple[list[str], list[str]]:
    """(open, landed) entries of `symbol`'s blocked_on (nemik:W443).

    A local W<n> that is done, or dropped into residue, has landed. Anything else (a local card
    still open, another repo's card, free text) is open: this tool cannot see another repo's state,
    so it does not guess.

    Returns:
        The open entries, and the landed ones.

    """
    data = table(json.loads(state.read_text(encoding="utf-8")))
    cards = {str(w["symbol"]): w for w in tables(data.get("waypoints"))}
    dropped = {str(r["symbol"]) for r in tables(data.get("residue"))}
    entries = strings(cards.get(symbol, {}).get("blocked_on"))
    landed = [
        b
        for b in entries
        if b in dropped or (b in cards and cards[b].get("status") == "done")
    ]
    return [b for b in entries if b not in landed], landed


def run_writer(argv: list[str]) -> tuple[int, str]:
    """Run the one writer, mikemol-paths-forward, with the given arguments (nemik:W587).

    The single place nemik-work and nemik-ask start the writer, so neither edits a queue itself.

    Args:
        argv: The arguments after the writer's path, for example `--state PATH --update W1`.

    Returns:
        The writer's exit status and its output (stderr when it failed, else stdout).

    """
    run = _spawn("mikemol-paths-forward", argv, None)
    if run.returncode:
        return run.returncode, run.stderr.strip() or run.stdout.strip()
    return 0, run.stdout.strip()


COMMITTER_TIMEOUT = 20  # seconds the commit tool may take to answer a read-only mode
NOT_INSTALLED, TIMED_OUT = 127, 124


def _spawn(
    tool: str, argv: list[str], timeout: int | None
) -> subprocess.CompletedProcess[str]:
    """Run one of the tools installed beside this interpreter, the only place nemik-work starts one.

    A tool that is not installed, or that outlasts `timeout`, is a completed process with status
    127 or 124 and no output, never an exception.

    Returns:
        The completed process.

    """
    path = Path(sys.executable).parent / tool
    if not path.is_file():
        return subprocess.CompletedProcess([tool], NOT_INSTALLED, "", "")
    try:
        return subprocess.run(
            [str(path), *argv],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess([tool], TIMED_OUT, "", "")


def run_committer(argv: list[str]) -> tuple[int, str]:
    """Run mikemol-commit with the given arguments, as run_writer runs the writer (nemik:W682).

    For its read-only modes (`REPO --in-gate --json`); a missing tool or a hang is an exit status,
    never an exception, since the caller is a check that must not fail for it.

    Args:
        argv: The arguments after the tool's path.

    Returns:
        The exit status and the standard output; 127 and nothing when the tool is not installed,
        124 and nothing after a timeout.

    """
    run = _spawn("mikemol-commit", argv, COMMITTER_TIMEOUT)
    return run.returncode, run.stdout


def named_waypoints(rows: object) -> set[str]:
    """Read the waypoints out of `mikemol-commit --in-gate --json` (a list of stack entries).

    Returns:
        Every waypoint any entry names; nothing for an answer that is not a list of entries.

    """
    named: set[str] = set()
    if not isinstance(rows, list):
        return named
    for row in rows:
        held = row.get("waypoints") if isinstance(row, dict) else None
        if isinstance(held, list):
            named.update(str(w) for w in held)
    return named


def in_gate(repo_dir: Path) -> set[str]:
    """Name the waypoints a queued or gating commit stack of this repo carries (nemik:W682, W633).

    A card in the commit gate is being worked, however long the gate takes. The list comes from
    mikemol-commit's own public mode (`--in-gate --json`), never from its private files under
    .git/mtools. A missing tool, a failure or an unreadable answer names nothing.

    Returns:
        The waypoint symbols of the live stacks.

    """
    code, out = run_committer([str(repo_dir), "--in-gate", "--json"])
    if code != 0:
        return set()
    try:
        rows: object = json.loads(out)
    except ValueError:
        return set()
    return named_waypoints(rows)


def plan(current: list[str], symbol: str) -> list[tuple[str, str]]:
    """(symbol, status) updates that mark `symbol` working and touch no other card.

    There is no one-working-card limit (operator 2026-10-15, host 695f3e0a line 68086): a round of
    cards being built, queued or gating are all working, so no working card is ever demoted.

    Returns:
        The (symbol, status) updates; none when the card is already working.

    """
    return [] if symbol in current else [(symbol, "working")]


class Options(argparse.Namespace):
    """The parsed command line of nemik-work (nemik:W1187)."""

    symbol: str
    state: Path
    dry_run: bool
    force: bool


def main(argv: list[str] | None = None) -> int:
    """nemik-work: mark one card working and clear its landed blockers, touching no other card.

    Returns:
        0 when done, 2 when the card is blocked, else the writer's nonzero code.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-work", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("symbol", help="the waypoint to work, W<n>")
    ap.add_argument(
        "--state",
        type=Path,
        default=Path(".claude/paths-forward.json"),
        help="the queue file (default: .claude/paths-forward.json here)",
    )
    ap.add_argument("--dry-run", action="store_true", help="print the updates only")
    ap.add_argument(
        "--force",
        action="store_true",
        help="work it even though blocked_on names something not known to have landed",
    )
    args = ap.parse_args(argv, namespace=Options())
    still, landed = blockers(args.state, args.symbol)
    if still and not args.force:
        # nemik:W443: working a blocked card left it 'working' with a stale blocked_on (W441).
        print(
            f"nemik-work: {args.symbol} is blocked on {', '.join(still)}; "
            "land or unblock those first, or pass --force",
            file=sys.stderr,
        )
        return 2
    steps = plan(working(args.state), args.symbol)
    for symbol, status in steps:
        note = f" (cleared landed blocker(s): {', '.join(landed)})" if landed else ""
        print(f"{symbol} -> {status}{note}")
        if args.dry_run:
            continue
        cmd = ["--state", str(args.state), "--update", symbol, "--status", status]
        if landed:
            # keep only what is still open; with nothing open the list is emptied
            cmd += ["--blocked-on", *still]
        code, said = run_writer(cmd)
        if code:
            print(said, file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
