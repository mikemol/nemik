# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W330: nemik-work W<n>: make W<n> the one working card.

The lifecycle says exactly one card is working at a time (data/workflows.toml); nemik-check warns on
two, and the pre-commit hook refuses a code commit with none. This does the whole move in one command:
every OTHER working card goes back to `ready`, then W<n> is marked `working`, all through the one
writer, mikemol-paths-forward. It never edits the queue file itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def working(state: Path) -> list[str]:
    """The symbols of the cards currently working, read from the queue file."""
    data = json.loads(state.read_text())
    return [
        w["symbol"] for w in data.get("waypoints", []) if w.get("status") == "working"
    ]


def blockers(state: Path, symbol: str) -> tuple[list[str], list[str]]:
    """(open, landed) entries of `symbol`'s blocked_on (nemik:W443).

    A local W<n> that is done, or dropped into residue, has landed. Anything else (a local card
    still open, another repo's card, free text) is open: this tool cannot see another repo's state,
    so it does not guess.
    """
    data = json.loads(state.read_text())
    cards = {w["symbol"]: w for w in data.get("waypoints", [])}
    dropped = {r["symbol"] for r in data.get("residue", [])}
    entries = cards.get(symbol, {}).get("blocked_on") or []
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
    writer = str(Path(sys.executable).parent / "mikemol-paths-forward")
    run = subprocess.run([writer, *argv], capture_output=True, text=True, check=False)
    if run.returncode:
        return run.returncode, run.stderr.strip() or run.stdout.strip()
    return 0, run.stdout.strip()


def plan(current: list[str], symbol: str) -> list[tuple[str, str]]:
    """(symbol, status) updates that leave `symbol` the only working card."""
    return [(s, "ready") for s in current if s != symbol] + (
        [] if symbol in current else [(symbol, "working")]
    )


def main(argv: list[str] | None = None) -> int:
    """nemik-work: make one card the single working card."""
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
    args = ap.parse_args(argv)
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
        displaced = symbol != args.symbol
        note = " (displaced: it was working)" if displaced else ""
        if not displaced and landed:
            note = f" (cleared landed blocker(s): {', '.join(landed)})"
        print(f"{symbol} -> {status}{note}")
        if args.dry_run:
            continue
        cmd = ["--state", str(args.state), "--update", symbol, "--status", status]
        if not displaced and landed:
            # keep only what is still open; with nothing open the list is emptied
            cmd += ["--blocked-on", *still]
        code, said = run_writer(cmd)
        if code:
            print(said, file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
