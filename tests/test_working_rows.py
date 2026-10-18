# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W681: each tick line that worked a card becomes a row: weight, leaf, directed."""

import json
from pathlib import Path

from nemik.metrics import ticks
from nemik.workrows import (
    cards_of,
    downstream,
    is_directed,
    is_leaf,
    working_rows,
)

CARDS: list[dict[str, object]] = [
    {"symbol": "W1", "enables": ["W2"], "blocked_on": [], "caused_by": None},
    {"symbol": "W2", "enables": ["W3"], "blocked_on": ["W1"], "caused_by": "W1"},
    {"symbol": "W3", "enables": [], "blocked_on": ["W2"], "caused_by": "github-8f"},
    {"symbol": "W4", "enables": [], "blocked_on": [], "caused_by": "operator"},
]
DOC: dict[str, list[dict[str, object]]] = {"waypoints": CARDS}
QUEUE = json.dumps(DOC)
LEDGER = (
    '2026-10-18T10:00:00Z  tick  W4  advanced  sweep    "a leaf"  evidence=x\n'
    '2026-10-18T09:00:00Z  tick  W1  advanced  unblock  "the root"  evidence=y\n'
    '2026-10-18T11:00:00Z  interrupt  W3  minted  -  "not a tick"  evidence=z\n'
    '2026-10-18T12:00:00Z  tick  W99  advanced  sweep  "not in the queue"  evidence=w\n'
)


def test_weight_follows_enables_transitively() -> None:
    """W1 enables W2 which enables W3: two cards lie downstream of W1, one of W2."""
    cards = cards_of(QUEUE)
    assert [downstream(cards, s) for s in ("W1", "W2", "W3")] == [2, 1, 0]


def test_a_leaf_is_a_card_nothing_waits_on() -> None:
    """W3 and W4 are waited on by nobody; W2 is waited on by W3 through blocked_on."""
    cards = cards_of(QUEUE)
    assert is_leaf(cards, "W4")
    assert not is_leaf(cards, "W2")
    assert not is_leaf(cards, "W1")


def test_directed_means_asked_for_by_someone_other_than_a_card() -> None:
    """A cause that is a peer or the operator is directed; a card or no cause is not."""
    cards = cards_of(QUEUE)
    assert is_directed(cards, "W3")
    assert is_directed(cards, "W4")
    assert not is_directed(cards, "W2")
    assert not is_directed(cards, "W1")


def test_text_that_is_not_a_queue_has_no_cards() -> None:
    """A torn file or a list at the top level reads as empty, never raises."""
    assert cards_of("{") == {}
    assert cards_of("[]") == {}


def test_only_tick_lines_naming_a_queued_card_make_rows(tmp_path: Path) -> None:
    """An interrupt line and a symbol the queue lacks are left out; rows come oldest first."""
    ledger = tmp_path / "ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    rows = working_rows(ticks("alpha", ledger), QUEUE)
    assert rows == [
        ("2026-10-18T09:00:00+00:00", "W1", 2, False, False),
        ("2026-10-18T10:00:00+00:00", "W4", 0, True, True),
    ]
