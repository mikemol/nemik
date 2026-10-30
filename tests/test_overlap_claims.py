# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W305 (mtools:W913): an OVERLAP row names who holds the work claim for its tag."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nemik.overlaps import Holder, parse_claims, read_claims, row

if TYPE_CHECKING:
    from pathlib import Path

CLAIMS = (
    "claim:label:touch:mtools:nemik owner=69232:142119 id=a658761a3fca age=22s\n"
    "claim:label:touch:mtools:locks owner=69232:142119 id=b1 age=22s\n"
    "something else entirely\n"
)


def test_claims_are_read_by_repo_and_tag() -> None:
    """Claims are read by repo and tag."""
    held = parse_claims(CLAIMS)
    assert held["mtools", "nemik"] == Holder("69232:142119", "22s")
    assert ("mtools", "locks") in held
    assert len(held) == 2


def test_an_overlap_row_names_the_holder_when_there_is_one() -> None:
    """An overlap row names the holder when there is one."""
    held = parse_claims(CLAIMS)
    assert (
        row("nemik", ["mtools:W913", "nemik:W305"], held)
        == "OVERLAP nemik: mtools:W913,nemik:W305  [mtools held by 69232:142119 (22s)]"
    )
    assert row("other", ["a:W1", "b:W2"], held) == "OVERLAP other: a:W1,b:W2"
    assert row("nemik", ["a:W1", "b:W2"]) == "OVERLAP nemik: a:W1,b:W2"


def test_an_absent_membudget_reads_as_no_claims(tmp_path: Path) -> None:
    """An absent membudget reads as no claims."""
    assert read_claims(tmp_path / "no-such-membudget") is None
