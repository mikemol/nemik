# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W835: a count or age that moves is not a new finding, so the delta does not reprint it."""

from nemik.digest import delta

AGE_BEFORE = (
    "  Info      --     24 ready cards untouched for 2.2 d (oldest W1513, 3.6 d)"
)
AGE_AFTER = (
    "  Info      --     24 ready cards untouched for 2.3 d (oldest W1513, 3.7 d)"
)
TICKS_BEFORE = "  Warning   W1642  has kept nemik:W702 waiting 51 loop ticks (SLA 48)"
TICKS_AFTER = "  Warning   W1642  has kept nemik:W702 waiting 52 loop ticks (SLA 48)"
HEADER = "OK        nemik"
NOTE = "unchanged lines not shown (nemik-check --digest without --since)"


def test_an_info_line_whose_age_moved_is_counted_not_reprinted() -> None:
    """The same Info shape with new numbers is left out and counted on its own line."""
    got = delta([HEADER, AGE_AFTER], [HEADER, AGE_BEFORE])
    assert got == [
        "1 Info lines only changed their numbers, not shown",
        f"1 {NOTE}",
    ]


def test_a_warning_whose_count_moved_prints_with_the_number_it_had() -> None:
    """A Warning may be news when its count moves: it prints once, saying what it was."""
    got = delta([HEADER, TICKS_AFTER], [HEADER, TICKS_BEFORE])
    assert got == [HEADER, f"{TICKS_AFTER}  (was 51, 48)", f"1 {NOTE}"]


def test_a_new_card_with_the_same_words_is_a_new_finding() -> None:
    """The digits of a waypoint symbol stay in the shape: W9 is not W1 with a moved number."""
    seen = [HEADER, "  Info      W1     next step names a.py"]
    now = [HEADER, "  Info      W9     next step names a.py"]
    got = delta(now, seen)
    assert got[:2] == [HEADER, "  Info      W9     next step names a.py"]


def test_unmoved_lines_are_still_just_counted() -> None:
    """The same digest twice is unchanged lines only, with no moved-number line."""
    got = delta([HEADER, AGE_BEFORE], [HEADER, AGE_BEFORE])
    assert got == [f"2 {NOTE}"]
