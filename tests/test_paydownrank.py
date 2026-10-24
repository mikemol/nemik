# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W989: paydown cards lead the ranking while their repo is behind, and nothing else moves."""

from nemik.paydownrank import lift_paydown, paydown_cards

TOUCHES = {
    "W1": ["file:ruff-baseline.json!w"],
    "W2": ["file:src/nemik/serve.py!w"],
    "W3": ["file:ruff-baseline.json"],
    "W4": [],
}


def test_a_card_touching_a_ratchet_file_pays_it_down() -> None:
    """The write suffix is ignored; a card on another file, or none, does not count."""
    assert paydown_cards(TOUCHES, ["ruff-baseline.json"]) == ["W1", "W3"]
    assert paydown_cards(TOUCHES, ["mypy-baseline.json"]) == []


def test_paydown_cards_lead_and_the_rest_keep_their_order() -> None:
    """The lifted cards keep their ranked order, then the others keep theirs."""
    order = ["W4", "W3", "W2", "W1"]
    assert lift_paydown(order, ["W1", "W3"]) == ["W3", "W1", "W4", "W2"]


def test_with_nothing_to_pay_down_the_order_is_unchanged() -> None:
    """A repo not behind lifts nothing."""
    order = ["W4", "W3", "W2", "W1"]
    assert lift_paydown(order, []) == order
