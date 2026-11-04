# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""working_unnamed: list the working cards that no live stack names (nemik:W1532, standing 17).

The submit's round check exempts only a card a live queued or gating stack names, so a card left
working after its stack landed, or marked before any stack carries it, is refused whenever a ready
round card is left out of the working set (stacks 890, 900 and 911). Run this at every landing and
before every submit; it reads the working cards through the writer's `--working-stale 0` and the
live stacks through `mikemol-commit --in-gate --json`, and writes nothing.
"""

import json
import sys
from pathlib import Path

from mikemol.procrun.proc import capture


def working_cards(listing: str) -> list[str]:
    """Read the card symbols from the writer's `--working-stale 0` listing.

    Returns:
        Each line's leading `W<n>` symbol, in listing order; the trailing summary line is skipped.

    """
    found: list[str] = []
    for line in listing.splitlines():
        words = line.split(maxsplit=1)
        head = words[0] if words else ""
        if head[:1] == "W" and head[1:].isdigit():
            found.append(head)
    return found


def named_cards(stacks_json: str) -> set[str]:
    """Read the cards a live stack names from `mikemol-commit --in-gate --json`.

    Returns:
        The `waypoints` of every queued or in-flight stack; empty for text that is not that shape.

    """
    try:
        parsed: object = json.loads(stacks_json)
    except ValueError:
        return set()
    stacks: list[dict[str, object]] = []
    if isinstance(parsed, list):
        stacks = [
            {str(k): v for k, v in s.items()} for s in parsed if isinstance(s, dict)
        ]
    named: set[str] = set()
    for stack in stacks:
        symbols = stack.get("waypoints")
        if isinstance(symbols, list):
            named.update(str(s) for s in symbols)
    return named


def successor_line(named: list[str]) -> str:
    """Say which cards a live stack names, as the successor the gate holds.

    Returns:
        `staged successor: <cards>` or `staged successor: none` (nemik:R216 finding 2).

    """
    return f"staged successor: {', '.join(named) or 'none'}"


def unnamed(listing: str, stacks_json: str) -> list[str]:
    """List the working cards that no live stack names.

    Returns:
        The working cards missing from every live stack, in listing order.

    """
    named = named_cards(stacks_json)
    return [card for card in working_cards(listing) if card not in named]


def main() -> int:
    """Run the two commands from this venv against this repo and say what is unnamed.

    Returns:
        0 when every working card is named, 1 when any is not, 2 when a command failed.

    """
    bin_dir = Path(sys.executable).parent
    root = Path(__file__).resolve().parents[1]
    state = root / ".claude" / "paths-forward.json"
    writer = str(bin_dir / "mikemol-paths-forward")
    listing = capture([writer, "--state", str(state), "--working-stale", "0"])
    stacks = capture(
        [str(bin_dir / "mikemol-commit"), str(root), "--in-gate", "--json"]
    )
    for done in (listing, stacks):
        if done.returncode:
            sys.stderr.write(f"working_unnamed: rc {done.returncode}: {done.stderr}\n")
            return 2
    working = working_cards(listing.stdout)
    named = sorted(named_cards(stacks.stdout))
    missing = unnamed(listing.stdout, stacks.stdout)
    sys.stdout.write(f"working: {', '.join(working) or 'none'}\n")
    sys.stdout.write(f"named by a live stack: {', '.join(named) or 'none'}\n")
    sys.stdout.write(f"{successor_line(named)}\n")
    sys.stdout.write(f"unnamed: {', '.join(missing) if missing else 'none unnamed'}\n")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
