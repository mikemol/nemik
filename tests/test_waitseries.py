# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W836: cross-repo wait rows become one sample per pair of repos."""

from nemik.waitseries import samples

OLDEST = 54
NEWER = 12
THREE = 3
ROWS = [
    ("luthen-observability", "nemik", OLDEST),
    ("luthen-observability", "nemik", NEWER),
    ("nemik", "mtools", NEWER),
    ("luthen-observability", "nemik", THREE),
]


def test_a_pair_of_repos_is_one_sample_with_its_oldest_wait_and_count() -> None:
    """Three luthen cards wait on nemik: one sample, 54 ticks old, count 3."""
    got = {(s.waiter, s.blocker): (s.oldest, s.count) for s in samples(ROWS)}
    assert got["luthen-observability", "nemik"] == (OLDEST, THREE)
    assert got["nemik", "mtools"] == (NEWER, 1)
    assert len(got) == len({(w, b) for w, b, _ in ROWS})


def test_the_oldest_wait_comes_first() -> None:
    """The longest-standing pair leads, so a dashboard's first row is the worst."""
    first = samples(ROWS)[0]
    assert (first.waiter, first.blocker) == ("luthen-observability", "nemik")


def test_no_waits_is_no_samples() -> None:
    """An empty fleet has nothing to publish."""
    assert samples([]) == []
