# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W758: a stamp with a UTC offset is read as the same moment, by hand, as Codon needs."""

from nemik.climate import levels_at
from nemik.verify import score_shingle

TOLERANCE = 1e-9
SHA = "abc123"


def test_a_stamp_is_the_same_moment_in_any_offset() -> None:
    """Issued 02:00+02:00 is 00:00 UTC; done at 12:00-04:00 is 16:00 UTC, inside +1d."""
    rows = [["2026-10-01T02:00:00+02:00", "a:W1", "+1d", "0", "1"]]
    done = {"a:W1": "2026-10-01T12:00:00-04:00"}
    got = score_shingle(rows, done, "2026-10-03T00:00:00+00:00", 0.5)
    assert abs(got["+1d"]) < TOLERANCE


def test_levels_place_an_event_by_its_utc_moment() -> None:
    """Ready at 01:00+02:00 is 23:00 the day before in UTC, so it counts at midnight UTC."""
    events = [("a:W1", "2026-10-02T01:00:00+02:00", "status", "", "ready", SHA)]
    assert levels_at(events, "2026-10-01T23:30:00+00:00")["a"]["ready"] == 1
    assert not levels_at(events, "2026-10-01T22:30:00+00:00")
