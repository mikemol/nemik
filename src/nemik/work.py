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
    args = ap.parse_args(argv)
    writer = str(Path(sys.executable).parent / "mikemol-paths-forward")
    steps = plan(working(args.state), args.symbol)
    for symbol, status in steps:
        print(f"{symbol} -> {status}")
        if args.dry_run:
            continue
        run = subprocess.run(
            [
                writer,
                "--state",
                str(args.state),
                "--update",
                symbol,
                "--status",
                status,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if run.returncode:
            print(run.stderr.strip() or run.stdout.strip(), file=sys.stderr)
            return run.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
