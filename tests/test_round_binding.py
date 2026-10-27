# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1135: the round board says which term bounded each repo's round."""

from nemik.roundgauges import binding_lines, round_board

UNREADABLE = ["# TYPE nemik_round_readable gauge", "nemik_round_readable 0"]
BOUND = [
    "# TYPE nemik_round_binding gauge",
    'nemik_round_binding{repo="a",term="supply"} 1',
    'nemik_round_binding{repo="b",term="landings"} 1',
]


def test_each_repo_states_the_term_that_bounded_its_round_sorted_by_repo() -> None:
    """One sample per repo at 1, the term a label; none when no repo states one."""
    assert binding_lines({"b": "landings", "a": "supply"}) == BOUND
    assert binding_lines({}) == []


def test_the_binding_is_published_even_when_the_round_file_cannot_be_read() -> None:
    """The terms come from the graph, not the file, like the ready counts."""
    assert round_board("", {}, None, {"b": "landings", "a": "supply"}) == [
        *UNREADABLE,
        *BOUND,
    ]
    assert round_board("", {}) == UNREADABLE
