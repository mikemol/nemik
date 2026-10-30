# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W367: nemik-import: tasks from another tool as writer commands, printed, never run.

nemik never writes a queue (the one writer is mikemol-paths-forward); an import is a list of the
writer's own commands that the receiving repo's loop reviews and runs. Sources are the formats
nemik exports (nemik.mspdi for MS Project, ProjectLibre and GanttProject; nemik.issues for issue
trackers), read back through their own `read`, so a round trip through another tool comes home
the same way.

Each task's `caused_by` is its source id (`<format>:<file>#<uid>`). A task whose source id some
card already carries is not added again; links to it use that card's symbol. The symbols the new
cards will get are predicted from the queue's counter (the writer issues them in order), so a
blocker can be cited by symbol in the same printed batch: every `--add` first, then the
`--update` lines that set blockers.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nemik.projection import Task


def _read(fmt: str, path: Path) -> list[Task]:
    text = path.read_text(encoding="utf-8")
    if fmt == "mspdi":
        from nemik.mspdi import read

        return read(text)
    from nemik.issues import read as read_issues

    return read_issues(text)


def commands(
    tasks: list[Task], fmt: str, source: str, state: Path, writer: str
) -> list[list[str]]:
    """List the writer's argv lists that add `tasks` to the queue at `state`, then link them.

    Returns:
        The writer's --add argv lists for tasks not yet in the queue, then the
        --update lists that mark them done or blocked.

    """
    queue = json.loads(state.read_text(encoding="utf-8"))
    cards = queue.get("waypoints", [])
    existing = {
        str(c.get("caused_by")): c["symbol"] for c in cards if c.get("caused_by")
    }
    counter = int(queue.get("counter", 0))
    sid = {t.cite: f"{fmt}:{source}#{t.uid}" for t in tasks}
    symbol: dict[str, str] = {}
    base = [writer, "--state", str(state)]
    adds: list[list[str]] = []
    for t in tasks:
        if sid[t.cite] in existing:
            symbol[t.cite] = existing[sid[t.cite]]
            continue
        counter += 1
        symbol[t.cite] = f"W{counter}"
        adds.append([*base, "--add", t.name or t.cite, "--caused-by", sid[t.cite]])
    updates: list[list[str]] = []
    for t in tasks:
        if sid[t.cite] in existing:
            continue
        me = symbol[t.cite]
        if t.done:
            updates.append([*base, "--update", me, "--status", "done"])
            continue
        blockers = [symbol[link.cite] for link in t.preds if link.cite in symbol]
        outside = [link.cite for link in t.preds if link.cite not in symbol]
        if blockers or outside:
            updates.append(
                [
                    *base,
                    "--update",
                    me,
                    "--status",
                    "blocked",
                    "--blocked-on",
                    *blockers,
                    *outside,
                    "--blocked-kind",
                    "agent",
                ]
            )
    return adds + updates


def main(argv: list[str] | None = None) -> int:
    """nemik-import: print the commands that bring another tool's tasks into a queue.

    Returns:
        0, after printing one shell-quoted command per line.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-import", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--from", dest="fmt", choices=("mspdi", "issues"), required=True)
    ap.add_argument("file", type=Path, help="the exported file to import")
    ap.add_argument(
        "--state",
        type=Path,
        default=Path(".claude/paths-forward.json"),
        help="the receiving queue (read for its counter and existing source ids; never written)",
    )
    args = ap.parse_args(argv)
    writer = str(Path(sys.executable).parent / "mikemol-paths-forward")
    for cmd in commands(
        _read(args.fmt, args.file), args.fmt, args.file.name, args.state, writer
    ):
        print(shlex.join(cmd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
