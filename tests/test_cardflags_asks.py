# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W971: the operator-ask category as a function of strings agrees with blocks."""

import pytest

from nemik import blocks, cardflags

ASKS = [
    "operator: decide which option to take",
    "operator: act run the drill on the host",
    "operator: act env -C /home/x /usr/bin/python -m tool --apply",
    "operator: act sudo systemctl restart thing",
    "operator: act bring the paper to the appointment",
    "ruled yes, keep holding",
    "approved by the operator on Tuesday",
    "event: the registry comes back",
    "once the PR merges",
    "a green tree and then ship it",
    "operator",
    "the operator (mike)",
    "user",
    "operator ok",
    "operator please look at this when you get the time",
    "mikemol: which one do you want?",
    "human: x",
    "",
]


@pytest.mark.parametrize("text", ASKS)
def test_the_category_agrees_with_the_graph_reference(text: str) -> None:
    """Each ask lands in the category blocks.operator_category gives it."""
    assert cardflags.operator_category(text) == blocks.operator_category(text)


def test_the_branches_are_all_reached() -> None:
    """The table is worth something only if it hits needs-you, no-command, answered, more."""
    seen = {cardflags.operator_category(text) for text in ASKS}
    assert seen == {"needs-you", "no-command", "answered", "condition", "unstated"}


def test_several_texts_take_the_most_actionable_category() -> None:
    """needs-you beats a condition, which beats an answered, on the same card."""
    texts = ["once the PR merges", "operator: decide the layout", "ruled yes"]
    assert cardflags.ask_category(texts, "", "a", set()) == "needs-you"
    assert cardflags.ask_category(["ruled yes", "once x lands"], "", "a", set()) == (
        "condition"
    )


def test_a_bare_operator_reads_the_ask_from_an_operator_title() -> None:
    """The title carries the ask when blocked_on is a bare party name."""
    title = "OPERATOR: decide whether to restart the pod"
    assert cardflags.ask_category(["operator"], title, "a", set()) == "needs-you"
    assert cardflags.ask_category(["operator"], "an ordinary title", "a", set()) == (
        "unstated"
    )


def test_a_no_command_ask_in_an_errand_repo_is_an_errand() -> None:
    """The operator's own errands are not an unwritten tool."""
    texts = ["operator: act run the drill on the host"]
    assert cardflags.ask_category(texts, "", "life", {"life"}) == "errand"
    assert cardflags.ask_category(texts, "", "mtools", {"life"}) == "no-command"


def test_a_card_with_no_texts_is_unstated() -> None:
    """Blocked on the operator by kind alone, with nothing written."""
    assert cardflags.ask_category([], "", "a", set()) == "unstated"
