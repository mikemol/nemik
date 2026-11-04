# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""stampnote: append a dated note to a card's evidence through the queue's one writer (nemik:W1568).

A G0 is written BEFORE the first edit and carries its own clock reading, so the time on the note is
the time it was written, never one typed by hand. This replaces a scratch script that was reaped
(nemik:R210 finding 3): the tool lives in tools/ with a test. It writes only through
`mikemol-paths-forward --update SYMBOL --evidence-append`.

Two checks label the stamp itself (nemik:R214 finding 1, file retro-r214.json): `[LATE ...]` when
a path in the card's manifest is already modified in the working tree, so the stamp is written
after the edit and says so; `[PACE-STALE n min]` when the note quotes a `pace read stamp <time>`
more than ten minutes before the stamp.

    .venv/bin/python3 tools/stampnote.py W1586 G0 "gate empty since ..."
"""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from mikemol.procrun.proc import capture

MIN_ARGS = 3
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
PACE_STAMP = re.compile(
    r"pace read(?: of)? (?:stamp )?(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"
)
STALE_MINUTES = 10
SECONDS_PER_MINUTE = 60
STATUS_PATH_AT = 3


def pace_age_minutes(now: datetime, text: str) -> int | None:
    """Say how old the pace read a note quotes is at the stamp.

    Returns:
        Whole minutes between the quoted `pace read stamp <time>` and `now`, or None when the
        note quotes none.

    """
    found = PACE_STAMP.search(text)
    if found is None:
        return None
    at = datetime.strptime(found[1], STAMP_FORMAT).replace(tzinfo=UTC)
    return int((now - at).total_seconds() // SECONDS_PER_MINUTE)


def late_paths(manifest: list[str], porcelain: str) -> list[str]:
    """Pick the manifest paths that `git status --porcelain` already lists as changed.

    Returns:
        The manifest paths present in the status, in manifest order.

    """
    changed = {line[STATUS_PATH_AT:].strip() for line in porcelain.splitlines()}
    return [path for path in manifest if path in changed]


def manifest_of(shown: str) -> list[str]:
    """Read a card's manifest from the writer's `--show SYMBOL` JSON.

    Returns:
        The manifest paths; empty for text that is not that shape or a card without one.

    """
    try:
        card = cast("dict[str, object]", json.loads(shown))
    except ValueError:
        return []
    manifest = card.get("manifest")
    return [str(p) for p in manifest] if isinstance(manifest, list) else []


def flags(now: datetime, text: str, late: list[str]) -> str:
    """Build the bracketed labels a stamp carries when a check fires.

    Returns:
        `[PACE-STALE n min]` and `[LATE: ...]` joined by a space, or an empty string.

    """
    labels: list[str] = []
    age = pace_age_minutes(now, text)
    if age is not None and age > STALE_MINUTES:
        labels.append(f"[PACE-STALE {age} min]")
    if late:
        labels.append(
            f"[LATE: {len(late)} manifest path(s) already modified: {', '.join(late)}]"
        )
    return " ".join(labels)


def stamp_text(now: datetime, label: str, text: str, marks: str = "") -> str:
    """Put the UTC clock reading of `now` between the label and the text.

    Returns:
        `<label> <YYYY-MM-DDTHH:MM:SSZ>: <marks> <text>`, the marks only when there are any.

    """
    body = f"{marks} {text}" if marks else text
    return f"{label} {now.astimezone(UTC).strftime(STAMP_FORMAT)}: {body}"


def command(writer: str, state: str, symbol: str, note: str) -> list[str]:
    """Give the writer's argv that appends `note` to `symbol`'s evidence.

    Returns:
        The argument vector, never shell-interpreted.

    """
    return [writer, "--state", state, "--update", symbol, "--evidence-append", note]


def main(argv: list[str]) -> int:
    """Stamp `argv` = SYMBOL LABEL TEXT onto the card and print the writer's answer.

    Returns:
        The writer's exit status, or 2 for a wrong number of arguments.

    """
    if len(argv) != MIN_ARGS:
        sys.stderr.write("usage: stampnote.py SYMBOL LABEL TEXT\n")
        return 2
    symbol, label, text = argv
    bin_dir = Path(sys.executable).parent
    root = Path(__file__).resolve().parents[1]
    writer = str(bin_dir / "mikemol-paths-forward")
    state = str(root / ".claude" / "paths-forward.json")
    now = datetime.now(UTC)
    shown = capture([writer, "--state", state, "--show", symbol]).stdout
    porcelain = capture(["git", "-C", str(root), "status", "--porcelain"]).stdout
    marks = flags(now, text, late_paths(manifest_of(shown), porcelain))
    done = capture(command(writer, state, symbol, stamp_text(now, label, text, marks)))
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
