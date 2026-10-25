# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1031: every nemik-check exit names its cause on a line a parser can read."""

from nemik.check import summary_line

FAILED = 2


def test_a_clean_survey_says_exit_zero_with_no_cause() -> None:
    """Nothing violates or is unreadable."""
    lines = ["OK        a", "OK        b"]
    assert summary_line(lines, 0) == "NEMIK-CHECK exit=0 violating=0 unreadable=0"


def test_an_unreadable_queue_is_named_not_left_to_a_missing_violates_line() -> None:
    """The case of 05:57Z-06:22Z: exit 1 with an UNREADABLE row and no VIOLATES row."""
    lines = ["OK        a", "UNREADABLE b: not json"]
    assert summary_line(lines, 1) == "NEMIK-CHECK exit=1 violating=0 unreadable=1"


def test_violations_and_unreadable_queues_are_counted_apart() -> None:
    """One of each gives exit 1 with both counts."""
    lines = ["VIOLATES  a", "  Violation W1 x", "UNREADABLE b: gone"]
    assert summary_line(lines, FAILED) == "NEMIK-CHECK exit=1 violating=1 unreadable=1"
