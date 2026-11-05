# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""landing_report: the stamps a G1 needs, in UTC, in one read (nemik:W1667, R244 finding 1).

Run it first after a landing. It prints the last landings of main as two full UTC stamps with the
gap since the one before (wall seconds), the stacks the gate holds with their begin stamp, the
`working_unnamed` lines, and the number of dirty paths in the tree. It writes nothing. The landing
stamps come from `git reflog --date=unix`, so no local time zone is ever read.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from mikemol.procrun.proc import capture
from working_unnamed import named_cards, successor_line, unnamed, working_cards

LANDINGS = 6
NS_PER_SECOND = 1_000_000_000


def landing_rows(reflog: str) -> list[tuple[datetime, str]]:
    """Read each `<sha> <name>@{<epoch>}: <subject>` reflog line into a UTC stamp and a short sha.

    Returns:
        The rows newest first; lines of any other shape are skipped.

    """
    rows: list[tuple[datetime, str]] = []
    for line in reflog.splitlines():
        head, _, rest = line.partition("@{")
        epoch, _, _ = rest.partition("}")
        if epoch.isdigit() and head.strip():
            sha = head.split()[0][:8]
            rows.append((datetime.fromtimestamp(int(epoch), UTC), sha))
    return rows


def stamp(when: datetime) -> str:
    """Format an instant as a full UTC stamp.

    Returns:
        `YYYY-MM-DDTHH:MM:SSZ`.

    """
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def landing_lines(rows: list[tuple[datetime, str]]) -> list[str]:
    """Say each landing with its stamp and the wall seconds since the landing before it.

    Returns:
        One line per row, newest first; the oldest row has no gap.

    """
    lines: list[str] = []
    for i, (when, sha) in enumerate(rows):
        gap = ""
        if i + 1 < len(rows):
            secs = int((when - rows[i + 1][0]).total_seconds())
            gap = f", {secs} s (wall) after the one before"
        lines.append(f"landed {stamp(when)} {sha}{gap}")
    return lines


def gate_lines(stacks_json: str) -> list[str]:
    """Say each stack the gate holds with its state and begin stamp.

    Returns:
        One line per stack; `gate: empty` when it holds none or the text is not that shape.

    """
    try:
        parsed: object = json.loads(stacks_json)
    except ValueError:
        return ["gate: empty"]
    stacks: list[dict[str, object]] = []
    if isinstance(parsed, list):
        stacks = [
            {str(k): v for k, v in s.items()} for s in parsed if isinstance(s, dict)
        ]
    lines: list[str] = []
    for item in stacks:
        began = item.get("began_ns")
        at = ""
        if isinstance(began, int):
            at = f" began {stamp(datetime.fromtimestamp(began / NS_PER_SECOND, UTC))}"
        lines.append(f"gate: {item.get('state')}{at} {item.get('waypoints')}")
    return lines or ["gate: empty"]


def main() -> int:
    """Print the landing stamps, the gate, the working marks and the dirty count for this repo.

    Returns:
        0 when every command ran, 2 when one failed.

    """
    bin_dir = Path(sys.executable).parent
    root = Path(__file__).resolve().parents[1]
    state = root / ".claude" / "paths-forward.json"
    git = ["git", "-C", str(root)]
    count = str(LANDINGS + 1)
    reflog = capture([*git, "reflog", "show", "--date=unix", "-n", count, "main"])
    status = capture([*git, "status", "--short"])
    stacks = capture(
        [str(bin_dir / "mikemol-commit"), str(root), "--in-gate", "--json"]
    )
    writer = str(bin_dir / "mikemol-paths-forward")
    listing = capture([writer, "--state", str(state), "--working-stale", "0"])
    for done in (reflog, status, stacks, listing):
        if done.returncode:
            sys.stderr.write(f"landing_report: rc {done.returncode}: {done.stderr}\n")
            return 2
    out = [stamp(datetime.now(UTC)) + " now"]
    out.extend(landing_lines(landing_rows(reflog.stdout)[:LANDINGS]))
    out.extend(gate_lines(stacks.stdout))
    working = working_cards(listing.stdout)
    named = sorted(named_cards(stacks.stdout))
    missing = unnamed(listing.stdout, stacks.stdout)
    out.extend(
        (
            f"working: {', '.join(working) or 'none'}",
            successor_line(named),
            f"unnamed: {', '.join(missing) if missing else 'none unnamed'}",
            f"dirty paths: {len(status.stdout.splitlines())}",
        )
    )
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
