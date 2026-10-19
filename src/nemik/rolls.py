# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W683: the run of consecutive tick rolls that advanced nothing, from a repo's ledger notes.

mikemol-paths-forward --tick-roll (mtools:W1589) closes a tick and opens the next in one step and
ends the ledger note with "[rolled; advanced N]", N being the cards a landed commit carried. A roll
that advanced nothing reads advanced 0, so a session that keeps rolling without landing is visible
in its own ledger. This module only reads that count; it imports nothing from nemik.
"""

import re

ROLLED = re.compile(r"\[rolled; advanced (\d+)\]")
NOT_A_ROLL = -1


def advanced(note: str) -> int:
    """Read the count a roll recorded.

    Args:
        note: A ledger line's note.

    Returns:
        N from "[rolled; advanced N]", or NOT_A_ROLL when the note is not a roll's.

    """
    found = ROLLED.search(note)
    if not found:
        return NOT_A_ROLL
    return int(found.group(1))


def idle_run(notes: list[str]) -> int:
    """Count the consecutive rolls at the end of a ledger that advanced nothing.

    Args:
        notes: The notes of a repo's tick lines, oldest first.

    Returns:
        How many of the newest rolls in a row read advanced 0; a line that is not a roll, or a roll
        that advanced a card, ends the run.

    """
    run = 0
    for note in reversed(notes):
        if advanced(note) != 0:
            break
        run += 1
    return run


def stalled(notes: list[str], ready: int, limit: int) -> bool:
    """Say whether the repo has rolled idle `limit` times in a row while ready cards exist.

    Args:
        notes: The notes of a repo's tick lines, oldest first.
        ready: How many cards are ready.
        limit: The run length that counts as stalled.

    Returns:
        True when the run reaches the limit and a ready card exists.

    """
    return ready > 0 and idle_run(notes) >= limit
