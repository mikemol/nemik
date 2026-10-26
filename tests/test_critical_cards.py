# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W453: the critical path computed from plain Cards alone, no graph."""

from nemik.cards import Card
from nemik.critical import critical_cards


def _card(
    cite: str, state: str = "ready", waits: tuple = (), enabled_by: tuple = ()
) -> Card:
    return Card(cite, state, "", tuple(waits), tuple(enabled_by))


def test_a_chain_and_a_tie_from_cards_alone() -> None:
    """The critical chain and its tie are read from the cards' edges, done cards not counting."""
    # r:W1 enables r:W2 and r:W3 (tied), both of which r:W4 waits on; r:W5 is done and does not count
    cards = {
        "r:W1": _card("r:W1"),
        "r:W2": _card("r:W2", enabled_by=("r:W1",)),
        "r:W3": _card("r:W3", enabled_by=("r:W1",)),
        "r:W4": _card("r:W4", waits=("r:W2", "r:W3")),
        "r:W5": _card("r:W5", "done", enabled_by=("r:W4",)),
    }
    found = critical_cards(cards)
    assert found.length == 3
    assert found.chain == ["r:W1", "r:W2", "r:W3", "r:W4"]
    assert found.rank == {"r:W1": 1, "r:W2": 2, "r:W3": 2, "r:W4": 3}
    assert (
        found.paths["r:W1"] == 2 and found.paths["r:W2"] == 1
    )  # two longest chains, tied
    assert "r:W5" not in found.slack


def test_a_scope_counts_only_its_cards() -> None:
    """A scope's critical chain counts the cards in that scope and no others."""
    cards = {
        "a:W1": _card("a:W1"),
        "a:W2": _card("a:W2", enabled_by=("a:W1",)),
        "b:W1": _card("b:W1", waits=("a:W2",)),
    }
    assert critical_cards(cards).length == 3
    assert critical_cards(cards, {"a:W1", "a:W2"}).length == 2
