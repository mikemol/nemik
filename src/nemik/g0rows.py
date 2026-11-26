# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2534 (W2450, nemik:R496 finding 1): which cards were worked with no G0 written first.

A G0 is the precommit a session writes to a card's evidence before the first edit of its files,
stamped by tools/stampnote.py as `G0 <UTC stamp>: ...`. The ledger holds the status rows, among
them `ready>working`. A card worked with no G0 stamped at or before its row is a finding; a G0 that
comes after the row is LATE and fires too (the precommit was written after the work began).

Pure: builtin types only and no import, so the Codon census compiles it. The stamps are fixed-width
UTC (`YYYY-MM-DDTHH:MM:SSZ`), so they compare as text.
"""

MARK = "G0 "
STAMP_WIDTH = 20  # len("2026-11-23T06:21:32Z")
NONE = "none"
LATE = "late"


def g0_stamps(evidence: str) -> list[str]:
    """Read the stamps of the G0 notes in a card's evidence.

    Args:
        evidence: The card's evidence text, with its appended notes.

    Returns:
        Each stamp that follows a `G0 ` mark and looks like a UTC stamp, in text order.

    """
    found: list[str] = []
    at = evidence.find(MARK)
    while at >= 0:
        start = at + len(MARK)
        stamp = evidence[start : start + STAMP_WIDTH]
        if len(stamp) == STAMP_WIDTH and stamp[10] == "T" and stamp[-1] == "Z":
            found.append(stamp)
        at = evidence.find(MARK, start)
    return found


def worked_without_g0(
    rows: list[tuple[str, str]], evidence: dict[str, str], cutover: str
) -> list[tuple[str, str, str]]:
    """Name the ready-to-working rows that have no G0 stamped at or before them.

    A row dated before the cut-over is not judged (history is a measured baseline, not a finding),
    and a symbol with no entry in `evidence` is not judged either (it is not a card of this queue).

    Args:
        rows: Each `ready>working` row as (its stamp, the card's symbol).
        evidence: The evidence text of each card, by symbol.
        cutover: The first stamp that counts, as `YYYY-MM-DDTHH:MM:SSZ`.

    Returns:
        (symbol, row stamp, NONE or LATE) per firing row, in row order: NONE when the card has no
        G0 note at all, LATE when its only G0 notes are stamped after the row.

    """
    out: list[tuple[str, str, str]] = []
    for stamp, symbol in rows:
        if stamp < cutover or symbol not in evidence:
            continue
        stamps = g0_stamps(evidence[symbol])
        if any(s <= stamp for s in stamps):
            continue
        out.append((symbol, stamp, LATE if stamps else NONE))
    return out
