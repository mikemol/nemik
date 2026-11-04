# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""stampnote: append a dated note to a card's evidence through the queue's one writer (nemik:W1568).

A G0 is written BEFORE the first edit and carries its own clock reading, so the time on the note is
the time it was written, never one typed by hand. This replaces a scratch script that was reaped
(nemik:R210 finding 3): the tool lives in tools/ with a test. It writes only through
`mikemol-paths-forward --update SYMBOL --evidence-append`.

    .venv/bin/python3 tools/stampnote.py W1586 G0 "gate empty since ..."
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

from mikemol.procrun.proc import capture

MIN_ARGS = 3


def stamp_text(now: datetime, label: str, text: str) -> str:
    """Put the UTC clock reading of `now` between the label and the text.

    Returns:
        `<label> <YYYY-MM-DDTHH:MM:SSZ>: <text>`.

    """
    return f"{label} {now.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}: {text}"


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
    done = capture(
        command(
            str(bin_dir / "mikemol-paths-forward"),
            str(root / ".claude" / "paths-forward.json"),
            symbol,
            stamp_text(datetime.now(UTC), label, text),
        )
    )
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
