# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1025: the round gauges say how much of each repo's working set lies outside its round."""

from pathlib import Path

import pytest

from nemik.pacepublish import epoch_seconds
from nemik.roundgauges import gauge_lines, read_round, round_board
from nemik.serve import working_cards

RECORDED = Path(__file__).parent / "fixtures" / "round" / "round.jsonl"
SECONDS = 1792886400
UNREADABLE = ["# TYPE nemik_round_readable gauge", "nemik_round_readable 0"]


def test_the_recorded_round_reads_as_each_repos_symbols_in_rank_order() -> None:
    """Alpha's two cards in rank order, beta's one, and the head's stamp."""
    stamp, rounds = read_round(RECORDED.read_text(encoding="utf-8"))
    assert stamp == "2026-10-25T09:00:00Z"
    assert rounds == {"alpha": ["W5", "W2"], "beta": ["W1"]}


def test_a_card_worked_outside_the_round_is_drift() -> None:
    """Alpha works W5 and W9: W9 is outside, so drift is a half; beta works nothing."""
    lines = gauge_lines(
        RECORDED.read_text(encoding="utf-8"), {"alpha": ["W5", "W9"]}, SECONDS
    )
    assert 'nemik_round_size{repo="alpha"} 2' in lines
    assert 'nemik_round_working{repo="alpha"} 2' in lines
    assert 'nemik_round_outside{repo="alpha"} 1' in lines
    assert 'nemik_round_drift{repo="alpha"} 0.5' in lines
    assert 'nemik_round_drift{repo="beta"} 0' in lines


def test_a_repo_worked_but_absent_from_the_round_is_all_outside() -> None:
    """A round of size 0 and one working card: that card is outside, drift 1."""
    lines = gauge_lines(
        RECORDED.read_text(encoding="utf-8"), {"gamma": ["W7"]}, SECONDS
    )
    assert 'nemik_round_size{repo="gamma"} 0' in lines
    assert 'nemik_round_drift{repo="gamma"} 1' in lines


def test_a_file_without_a_stamp_is_refused() -> None:
    """No head line, no round."""
    with pytest.raises(ValueError, match="no as_of"):
        read_round('{"repo": "a", "symbol": "W1", "rank": "1", "salience": "0"}\n')


def test_the_board_of_a_readable_round_dates_it_by_its_own_stamp() -> None:
    """Readable 1, the round's gauges, and as_of in seconds read from the file's head."""
    lines = round_board(RECORDED.read_text(encoding="utf-8"), {"alpha": ["W5"]})
    assert lines[:2] == ["# TYPE nemik_round_readable gauge", "nemik_round_readable 1"]
    assert f"nemik_round_as_of {epoch_seconds('2026-10-25T09:00:00Z')}" in lines
    assert 'nemik_round_drift{repo="alpha"} 0' in lines


def test_a_missing_or_refused_round_file_says_so_and_guesses_nothing() -> None:
    """Empty text and text with no stamp both publish readable 0 alone, never no gauge."""
    assert round_board("", {"alpha": ["W5"]}) == UNREADABLE
    assert round_board("not a round\n", {}) == UNREADABLE


def test_the_working_cards_are_grouped_by_repo() -> None:
    """Only cards in state working, each under its repo; a node missing a field is skipped."""
    nodes: list[dict[str, object]] = [
        {"repo": "a", "symbol": "W1", "state": "working"},
        {"repo": "a", "symbol": "W2", "state": "ready"},
        {"repo": "b", "symbol": "W3", "state": "working"},
        {"repo": "a", "state": "working"},
    ]
    assert working_cards(nodes) == {"a": ["W1"], "b": ["W3"]}


def test_a_ready_card_a_commit_stack_names_is_being_worked_too() -> None:
    """nemik:W1062: a card in the gate under a stale ready status is in progress, not idle."""
    nodes: list[dict[str, object]] = [
        {"repo": "a", "symbol": "W1", "state": "ready", "stage": "gating"},
        {"repo": "a", "symbol": "W2", "state": "ready", "stage": ""},
    ]
    assert working_cards(nodes) == {"a": ["W1"]}
