# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2534: a card worked with no G0 written first is named, from a planted ledger."""

from nemik.g0rows import LATE, NONE, g0_stamps, worked_without_g0

CUTOVER = "2026-11-15T00:00:00Z"
WORKED = "2026-11-20T10:00:00Z"
BEFORE = "2026-11-20T09:00:00Z"
AFTER = "2026-11-20T11:00:00Z"


def _note(stamp: str) -> str:
    """Word a G0 note as tools/stampnote.py appends it to a card's evidence.

    Returns:
        The note text, stamped twice as the tool writes it.

    """
    return f"earlier text | {stamp}: G0 {stamp}: Precommit: this advances the card."


def test_the_stamps_of_the_g0_notes_are_read_in_order() -> None:
    """Each `G0 <stamp>` is read; a mark with no stamp after it, and none at all, give nothing."""
    text = _note(BEFORE) + " | " + _note(AFTER)
    assert g0_stamps(text) == [BEFORE, AFTER]
    assert g0_stamps("G0 later, not a stamp") == []
    assert g0_stamps("") == []


def test_a_g0_before_the_row_passes() -> None:
    """The precommit came first: nothing fires."""
    rows = [(WORKED, "W1")]
    assert worked_without_g0(rows, {"W1": _note(BEFORE)}, CUTOVER) == []


def test_a_g0_at_the_row_instant_passes() -> None:
    """At or before counts."""
    assert worked_without_g0([(WORKED, "W1")], {"W1": _note(WORKED)}, CUTOVER) == []


def test_no_g0_fires_as_none() -> None:
    """MUTANT: a card with evidence but no G0 note must not read as clean."""
    found = worked_without_g0([(WORKED, "W1")], {"W1": "just evidence"}, CUTOVER)
    assert found == [("W1", WORKED, NONE)]


def test_a_g0_after_the_row_is_late_and_fires() -> None:
    """The precommit was written after the work began."""
    found = worked_without_g0([(WORKED, "W1")], {"W1": _note(AFTER)}, CUTOVER)
    assert found == [("W1", WORKED, LATE)]


def test_a_row_before_the_cutover_is_not_judged() -> None:
    """History is a measured baseline, not a finding."""
    old = "2026-11-01T10:00:00Z"
    assert worked_without_g0([(old, "W1")], {"W1": ""}, CUTOVER) == []


def test_a_symbol_not_in_the_evidence_is_not_judged() -> None:
    """A row for a card the queue does not hold (dropped, another repo) cannot be judged."""
    assert worked_without_g0([(WORKED, "W9")], {"W1": ""}, CUTOVER) == []


def test_each_row_is_judged_on_its_own_stamp() -> None:
    """A G0 written between two rows covers the second, not the first."""
    rows = [("2026-11-20T08:00:00Z", "W1"), (WORKED, "W1")]
    found = worked_without_g0(rows, {"W1": _note(BEFORE)}, CUTOVER)
    assert found == [("W1", "2026-11-20T08:00:00Z", LATE)]
