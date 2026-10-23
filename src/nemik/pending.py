# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pending: the cards closed lately, from the queues' own text (nemik:W888, W546).

delivery.owed keeps one letter per cross-repo edge, once, but only a witness applying a card
(nemik-witnesses --apply) calls it. A card the writer marked done, or dropped to residue, sends
nothing, since the writer fires no event on close (mtools:W1215 only prunes the blockers). This
reads the closing stamps already in each queue: a done card's `completed`, a dropped card's
`dropped_at`. The delivery record keeps the letters from repeating, so this only has to say which
cards closed since a day, and the caller hands each to witnesses.deliver. Imports only json, so
the Codon census compiles it.
"""

import json

Closed = tuple[str, str, str]  # (repo, symbol, outcome: "done" or "dropped")
DAY_DIGITS = 8


def day_of(stamp: str) -> str:
    """Read the date out of either stamp form the writer uses.

    Args:
        stamp: `20261004T205827Z` (completed) or `2026-09-26T18:57:05Z` (dropped_at).

    Returns:
        `YYYYMMDD`; empty when the stamp holds no date.

    """
    digits = stamp.replace("-", "")[:DAY_DIGITS]
    return digits if len(digits) == DAY_DIGITS and digits.isdigit() else ""


def _symbols(items: object, status: str, field: str, since: str) -> list[str]:
    """List the symbols of cards whose stamp is on or after a day.

    Args:
        items: A queue's `waypoints` or `residue`, as json parsed it.
        status: The status a waypoint must have; empty to take every entry (residue).
        field: The stamp field to read, `completed` or `dropped_at`.
        since: `YYYYMMDD`, the first day that counts.

    Returns:
        The cards that closed on or after `since`, in file order.

    """
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for card in items:
        if not isinstance(card, dict):
            continue
        if status and str(card.get("status")) != status:
            continue
        day = day_of(str(card.get(field) or ""))
        if day and day >= since:
            out.append(str(card.get("symbol")))
    return out


def closed_since(queues: dict[str, str], since: str) -> list[Closed]:
    """Find the cards closed on or after a day in every repo's queue.

    Args:
        queues: Each repo's name and the text of its paths-forward.json.
        since: `YYYYMMDD`, the first day that counts.

    Returns:
        (repo, symbol, outcome) for each done or dropped card, repos in name order and, within a
        repo, done cards before dropped ones; a queue that is not JSON is left out.

    """
    out: list[Closed] = []
    for repo in sorted(queues):
        try:
            doc: object = json.loads(queues[repo])
        except ValueError:
            continue
        if not isinstance(doc, dict):
            continue
        done = _symbols(doc.get("waypoints"), "done", "completed", since)
        dropped = _symbols(doc.get("residue"), "", "dropped_at", since)
        out.extend((repo, symbol, "done") for symbol in done)
        out.extend((repo, symbol, "dropped") for symbol in dropped)
    return out
