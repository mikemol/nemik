# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1719: a mark whose as_of nemik cannot read reads stale and is counted, never silent."""

import json

from nemik.marks import STALE, bad_instants, mark_source, marks_from_text

NOW = "2026-10-08T12:00:00+00:00"
VERSION = "v1"
UNREAD = 2  # W1 stamped +01:00 and W3 naive


def _line(symbol: str, as_of: str) -> str:
    fields: dict[str, object] = {
        "symbol": symbol,
        "policy_version": VERSION,
        "as_of": as_of,
    }
    return json.dumps(fields)


def test_a_mark_stamped_with_another_offset_reads_stale_and_is_counted() -> None:
    """A writer that began to stamp +01:00 would turn every card stale; the count names why."""
    text = "\n".join(
        [
            _line("W1", "2026-10-08T11:30:00+01:00"),
            _line("W2", "2026-10-08T11:30:00+00:00"),
            _line("W3", "2026-10-08T11:30:00"),
            _line("W4", "2026-10-08T11:30:00Z"),
        ]
    )
    marks, unreadable = marks_from_text(text)
    assert unreadable == 0
    assert mark_source(marks, "W1", NOW, VERSION) == STALE
    assert mark_source(marks, "W3", NOW, VERSION) == STALE
    assert bad_instants(marks) == UNREAD


def test_marks_the_reader_reads_are_not_counted() -> None:
    """MUTANT: counting a readable mark would cry wolf on every healthy marks file."""
    marks, _ = marks_from_text(_line("W1", "2026-10-08T11:30:00+00:00"))
    assert bad_instants(marks) == 0
    assert bad_instants({}) == 0
