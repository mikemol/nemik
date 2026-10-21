# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W751: the host-side landings document round-trips between the writer and the server."""

import pytest

from nemik.landings import Landing, document, read_document

STAMP = "2026-10-21T06:00:00Z"
ROWS = [
    Landing("nemik", "d48dfe1", "W827", 692, "2026-10-21T02:31:49Z"),
    Landing("mtools", "f39dd23", "-", 938, "2026-10-21T05:39:49Z"),
]


def test_the_stamp_and_every_landing_come_back_as_written() -> None:
    """Write then read gives the same stamp and rows, in order."""
    as_of, rows = read_document(document(ROWS, STAMP))
    assert as_of == STAMP
    assert [(r.repo, r.sha, r.card, r.gate_s, r.when) for r in rows] == [
        (r.repo, r.sha, r.card, r.gate_s, r.when) for r in ROWS
    ]


def test_an_empty_series_is_still_a_document() -> None:
    """No landings reads back as the stamp and nothing else."""
    as_of, rows = read_document(document([], STAMP))
    assert as_of == STAMP
    assert rows == []


def test_a_document_without_a_stamp_is_refused() -> None:
    """The freshness check needs the stamp, so a file without one is an error."""
    with pytest.raises(ValueError, match="as_of"):
        read_document("[]")
