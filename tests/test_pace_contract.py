# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1120: the pace writer's rows have the keys luthen's egress gate admits, from one fixture.

luthen removed ratchet-pace.json when 578a6db added `value` and `horizon` to the rows (W1119). The
fixture is the literal file luthen's SHAPE test reads too (luthen-observability:W1686, the
round.jsonl pattern of W1033): a field added on either side fails the other's test before it lands.
"""

from pathlib import Path

from nemik.pacepublish import read_extras, read_pace
from nemik.pacerun import pace_document

FIXTURE = Path(__file__).parent / "fixtures" / "pace" / "ratchet-pace.jsonl"
STAMP = "2026-10-26T17:00:14Z"
KEYS = ["repo", "ratchet", "state", "observed", "required", "value", "horizon"]
EXPORT = Path(__file__).parent / "fixtures" / "ratchet" / "nemik_export.jsonl"


def _keys(row: str) -> list[str]:
    """List a row's keys in the order it writes them.

    Returns:
        The keys of the flat object, textually, so no json call is referenced.

    """
    return [part.split('"')[1] for part in row.strip("{}").split(", ") if part]


def test_the_fixture_reads_through_the_pace_readers() -> None:
    """The literal file luthen copies parses with read_pace and states value and horizon."""
    text = FIXTURE.read_text(encoding="utf-8")
    as_of, window, rows = read_pace(text)
    assert (as_of, window, len(rows)) == (STAMP, 10, len(text.splitlines()) - 1)
    assert len(read_extras(text)) == len(rows)


def test_every_fixture_row_has_exactly_the_admitted_keys() -> None:
    """The fixture is the contract: seven keys, in this order, numbers as quoted text."""
    rows = FIXTURE.read_text(encoding="utf-8").splitlines()[1:]
    assert all(_keys(row) == KEYS for row in rows)


def test_the_writers_rows_have_the_fixtures_keys() -> None:
    """A row pace_document writes has the fixture's keys, so adding a field fails here first."""
    text = pace_document(EXPORT.read_text(encoding="utf-8"), "", STAMP)
    rows = text.splitlines()[1:]
    assert rows
    assert all(_keys(row) == KEYS for row in rows)
    assert _keys(text.splitlines()[0]) == ["as_of", "window"]
