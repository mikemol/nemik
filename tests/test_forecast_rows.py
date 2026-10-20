# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W747: an issue is laid out as one shingle row per lead."""

from nemik.forecastshingle import shingle_rows

ISSUED = "2026-10-20T03:00:00+00:00"


def test_each_lead_of_an_issue_is_its_own_row() -> None:
    """The rows carry issue time, station, lead, age and chance, in the order of the chances."""
    rows = shingle_rows(ISSUED, "a:W7", 2.5, {"+1d": 0.25, "+3d": 0.5})
    assert rows == [
        [ISSUED, "a:W7", "+1d", "2.5", "0.25"],
        [ISSUED, "a:W7", "+3d", "2.5", "0.5"],
    ]


def test_no_chances_give_no_rows() -> None:
    """An issue with nothing to say appends nothing."""
    assert shingle_rows(ISSUED, "a:W7", 0.0, {}) == []
