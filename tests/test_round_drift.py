# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1025: the round file and the drift gauges say what the rounds and working sets are."""

from nemik.roundfile import drift_text, metric_lines, round_text

STAMP = "2026-10-25T00:00:00Z"
SECONDS = 1792886400


def test_the_file_has_a_head_and_a_line_per_round_card() -> None:
    """Two cards of one repo, one of another, in the order given."""
    text = round_text(
        STAMP, [("a", [("W5", 1, "9.0"), ("W2", 2, "4.5")]), ("b", [("W1", 1, "0.5")])]
    )
    assert text.splitlines() == [
        '{"as_of": "2026-10-25T00:00:00Z"}',
        '{"repo": "a", "symbol": "W5", "rank": "1", "salience": "9.0"}',
        '{"repo": "a", "symbol": "W2", "rank": "2", "salience": "4.5"}',
        '{"repo": "b", "symbol": "W1", "rank": "1", "salience": "0.5"}',
    ]


def test_drift_is_the_share_outside_and_zero_when_nothing_is_worked() -> None:
    """One of four outside is a quarter; none worked is zero, not a division by zero."""
    assert drift_text(1, 4) == "0.25"
    assert drift_text(0, 0) == "0"


def test_the_gauges_carry_each_repo_and_the_age_stamp() -> None:
    """Size, working, outside and drift per repo, then the as_of in seconds."""
    lines = metric_lines([("a", 2, 4, 1)], SECONDS)
    assert 'nemik_round_size{repo="a"} 2' in lines
    assert 'nemik_round_working{repo="a"} 4' in lines
    assert 'nemik_round_outside{repo="a"} 1' in lines
    assert 'nemik_round_drift{repo="a"} 0.25' in lines
    assert lines[-1] == f"nemik_round_as_of {SECONDS}"
