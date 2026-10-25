# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W996: a real range-query answer of the ratchet gauge reads into ordered value lists."""

from pathlib import Path

import pytest

from nemik.ratchetseries import series_of

FIXTURE = Path(__file__).parent / "fixtures" / "ratchet" / "mtools_series.json"


def test_the_recorded_answer_is_one_series_of_five_values() -> None:
    """Read the exit baseline of mtools: five hourly samples, all 8 entries."""
    got = series_of(FIXTURE.read_text(encoding="utf-8"))
    assert got == [("mtools", "corpus/exit-baseline.txt", [8, 8, 8, 8, 8])]


def test_the_phantom_repo_and_unreadable_samples_are_left_out() -> None:
    """A tree series is dropped; a sample that is not a time and a number is skipped."""
    answer = (
        '{"status":"success","data":{"resultType":"matrix","result":['
        '{"metric":{"repo":"tree","ratchet":"x"},"values":[[1,"3"]]},'
        '{"metric":{"repo":"a","ratchet":"y"},"values":[[2,"5"],[1,"7"],["bad",1]]}'
        "]}}"
    )
    assert series_of(answer) == [("a", "y", [7, 5])]


def test_an_answer_that_is_not_a_success_is_refused() -> None:
    """An error answer raises rather than reading as an empty series."""
    with pytest.raises(TypeError, match="not a successful"):
        series_of('{"status":"error"}')
