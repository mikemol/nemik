# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pendingdeliver: announce the cards the writer closed, once (nemik:W889, W546).

A card marked done by the writer, or dropped to residue, reaches its cross-repo waiters only if a
witness applied it. pending.closed_since lists the cards closed in the last few days from the
queues' own stamps; witnesses.deliver writes one letter per edge and its delivery record keeps a
rerun from writing it again. This joins the two. Run it from a timer as
`python -m nemik.pendingdeliver`, so no closed card is left unannounced. It is a module of its own
and not a flag of nemik-witnesses because it imports witnesses, which would make the flag circular.
"""

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from nemik.pending import closed_since
from nemik.witnesses import deliver, queue_texts

DEFAULT_DAYS = 3


class _Options(argparse.Namespace):
    """The command line, typed."""

    root: Path
    days: int


def since_day(today: date, days: int) -> str:
    """Name the first day that counts as lately.

    Args:
        today: The current date.
        days: How many days back a closed card is still announced.

    Returns:
        `YYYYMMDD` of today minus `days`.

    """
    return (today - timedelta(days=days)).strftime("%Y%m%d")


def sweep(root: Path, today: date, days: int = DEFAULT_DAYS) -> list[Path]:
    """Write the letters owed for every card closed in the last few days.

    Args:
        root: The fleet root, holding each repo's directory.
        today: The current date.
        days: How many days back a closed card is still announced.

    Returns:
        The letters written this run; none for an edge the delivery record already shows sent.

    """
    queues = queue_texts(root)
    written: list[Path] = []
    for repo, symbol, outcome in closed_since(queues, since_day(today, days)):
        written.extend(
            deliver(root, queues, (repo, symbol), outcome, today.isoformat())
        )
    return written


def main(argv: list[str] | None = None) -> int:
    """Announce the recently closed cards and print each letter written.

    Returns:
        0.

    """
    parser = argparse.ArgumentParser(
        prog="python -m nemik.pendingdeliver", description=__doc__
    )
    parser.add_argument("--root", type=Path, default=Path.home() / "github")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    options = parser.parse_args(argv, namespace=_Options())
    today = datetime.now(UTC).date()
    for letter in sweep(options.root, today, options.days):
        sys.stdout.write(f"LETTER {letter}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
