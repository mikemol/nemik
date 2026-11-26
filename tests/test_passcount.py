# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2517: the builder's pass counter, by outcome, survives its one-pass processes."""

import pytest

from nemik import passcount as pc

POD = "nemik-599c7b97fb-2z9mt"


def test_the_counts_file_round_trips() -> None:
    """What render writes, parse reads."""
    assert pc.parse(pc.render((7, 120))) == (7, 120)
    assert pc.render((0, 0)) == "built 0\nskipped 0\n"


def test_a_missing_or_damaged_file_starts_the_counter_over() -> None:
    """No file, junk, a negative or a non-number read as zero for that outcome, never an error."""
    assert pc.parse("") == (0, 0)
    assert pc.parse("garbage\nbuilt x\nskipped -3\n") == (0, 0)
    assert pc.parse("built 4\nskipped nope\n") == (4, 0)
    assert pc.parse("built 4 extra\nskipped 2\n") == (0, 2)


def test_a_pass_adds_one_to_its_outcome_only() -> None:
    """Built and skipped are counted apart; another word is a defect, never a count."""
    assert pc.bump((3, 9), pc.BUILT) == (4, 9)
    assert pc.bump((3, 9), pc.SKIPPED) == (3, 10)
    with pytest.raises(ValueError, match="not a pass outcome"):
        pc.bump((3, 9), "failed")


def test_the_counter_is_prometheus_text_with_both_outcomes_always_present() -> None:
    """A zero outcome is a sample, not an absence."""
    lines = pc.lines((0, 5), POD)
    assert lines[0].startswith("# HELP nemik_publish_passes_total ")
    assert lines[1] == "# TYPE nemik_publish_passes_total counter"
    assert lines[2] == f'nemik_publish_passes_total{{outcome="built",pod="{POD}"}} 0'
    assert lines[3] == f'nemik_publish_passes_total{{outcome="skipped",pod="{POD}"}} 5'


def test_merging_replaces_the_earlier_counter_and_keeps_every_other_line() -> None:
    """A metrics file with an old copy ends with exactly one current copy."""
    base = "# TYPE nemik_snapshot_published_seconds gauge\nnemik_snapshot_published_seconds 1\n"
    once = pc.merge(base, pc.lines((1, 2), POD))
    twice = pc.merge(once, pc.lines((1, 3), POD))
    assert twice.startswith(base)
    assert twice.count("nemik_publish_passes_total{") == len(pc.OUTCOMES)
    assert f'outcome="skipped",pod="{POD}"}} 3' in twice
    assert f'outcome="skipped",pod="{POD}"}} 2' not in twice
    assert twice.endswith("\n")
    assert pc.merge("", pc.lines((0, 0), POD)).count("\n") == len(pc.lines((0, 0), POD))
