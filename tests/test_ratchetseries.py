# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W996: a real range-query answer of the ratchet gauge reads into ordered value lists."""

from pathlib import Path

import pytest

from nemik.ratchetseries import ended_series, export_series, series_of

FIXTURE = Path(__file__).parent / "fixtures" / "ratchet" / "mtools_series.json"
EXPORT = Path(__file__).parent / "fixtures" / "ratchet" / "nemik_export.jsonl"


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


def test_the_recorded_export_is_one_value_per_gate_run_for_each_ratchet() -> None:
    """Nemik's three baselines, seven gate runs each, sorted by ratchet name."""
    got = export_series(EXPORT.read_text(encoding="utf-8"))
    assert [(repo, ratchet) for repo, ratchet, _ in got] == [
        ("nemik", "codon-baseline.json"),
        ("nemik", "mypy-baseline.json"),
        ("nemik", "ruff-baseline.json"),
    ]
    assert got[0][2] == [226, 228, 228, 230, 230, 230, 230]
    assert got[2][2] == [1025, 1025, 1025, 1025, 1025, 1024, 1024]


def test_a_series_that_ended_is_named_but_kept() -> None:
    """Repo a's x stopped while y went on: x is named as ended and still read; quiet b is not."""
    text = (
        '{"metric":{"repo":"a","ratchet":"x"},"values":[5,5],"timestamps":[1000,2000]}\n'
        '{"metric":{"repo":"a","ratchet":"y"},"values":[7,7,7],"timestamps":'
        "[1000,2000,900000]}\n"
        '{"metric":{"repo":"b","ratchet":"z"},"values":[3],"timestamps":[1000]}\n'
    )
    assert ended_series(text) == [("a", "x")]
    got = export_series(text)
    assert [(repo, ratchet) for repo, ratchet, _ in got] == [
        ("a", "x"),
        ("a", "y"),
        ("b", "z"),
    ]


def test_an_export_line_out_of_order_is_sorted_by_its_timestamps() -> None:
    """Values follow their own timestamps, and a line that is no series is skipped."""
    text = (
        '{"metric":{"repo":"a","ratchet":"y"},"values":[5,7],"timestamps":[20,10]}\n'
        "not json at all\n"
        '{"metric":{"repo":"tree","ratchet":"y"},"values":[1],"timestamps":[1]}\n'
    )
    assert export_series(text) == [("a", "y", [7, 5])]
