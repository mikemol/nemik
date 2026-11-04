# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1532: tools/working_unnamed.py lists the working cards no live stack names."""

from working_unnamed import named_cards, successor_line, unnamed, working_cards

LISTING = """\
W1545 0.0d Rewrite the fake writer in test_rank_apply.py.
W1544 0.0d Codemod w1544_tests.py: three checked wrappers.
# 2 working, none in flight, older than 0d
"""
STACKS = (
    '[{"key": "1", "state": "inflight", "waypoints": ["W1545"], "began_ns": 1},'
    ' {"key": "2", "state": "queued", "waypoints": ["W1546", "W1547"], "began_ns": null}]'
)


def test_the_successor_line_names_the_staged_cards_or_none() -> None:
    """The landing sensor says what is staged behind the stack that landed, or that nothing is."""
    assert successor_line(["W1", "W2"]) == "staged successor: W1, W2"
    assert successor_line([]) == "staged successor: none"


def test_the_working_cards_are_the_listings_symbols_without_its_summary_line() -> None:
    """Each leading W<n> is a card; the `# 2 working` summary and blank lines are not."""
    assert working_cards(LISTING) == ["W1545", "W1544"]
    assert working_cards("") == []


def test_every_waypoint_of_every_live_stack_is_named() -> None:
    """In-flight and queued stacks both name their waypoints; torn text names none."""
    assert named_cards(STACKS) == {"W1545", "W1546", "W1547"}
    assert named_cards("not json") == set()
    assert named_cards('{"waypoints": ["W1"]}') == set()


def test_a_working_card_no_stack_names_is_reported_and_the_rest_are_not() -> None:
    """W1544 is working and no stack names it; W1545 is named."""
    assert unnamed(LISTING, STACKS) == ["W1544"]
    assert unnamed(LISTING, "[]") == ["W1545", "W1544"]
    assert unnamed("", STACKS) == []
