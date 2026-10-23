# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Tests for pending: the cards closed lately, read from the queues' text (nemik:W888)."""

import json

from nemik.pending import closed_since, day_of

SINCE = "20261020"


def _queue(waypoints: list[dict[str, object]], residue: list[dict[str, object]]) -> str:
    body: dict[str, object] = {"waypoints": waypoints, "residue": residue}
    return json.dumps(body)


def test_both_stamp_forms_give_a_day() -> None:
    """Completed has no dashes, dropped_at has them; junk gives no day."""
    assert day_of("20261004T205827Z") == "20261004"
    assert day_of("2026-09-26T18:57:05Z") == "20260926"
    assert not day_of("")
    assert not day_of("soon")


def test_recent_done_and_dropped_cards_are_listed_in_order() -> None:
    """Done cards before dropped ones, repos by name; old and unstamped cards are left out."""
    queues = {
        "b": _queue(
            [
                {"symbol": "W2", "status": "done", "completed": "20261022T010101Z"},
                {"symbol": "W3", "status": "done", "completed": "20261001T010101Z"},
                {"symbol": "W4", "status": "done", "completed": None},
                {"symbol": "W5", "status": "ready", "completed": "20261022T010101Z"},
            ],
            [{"symbol": "W9", "dropped_at": "2026-10-21T05:00:00Z"}],
        ),
        "a": _queue(
            [{"symbol": "W1", "status": "done", "completed": SINCE + "T0Z"}], []
        ),
    }
    assert closed_since(queues, SINCE) == [
        ("a", "W1", "done"),
        ("b", "W2", "done"),
        ("b", "W9", "dropped"),
    ]


def test_a_queue_that_is_not_json_is_left_out() -> None:
    """One broken queue does not hide the others."""
    queues = {"bad": "{", "list": "[]", "ok": _queue([], [])}
    assert closed_since(queues, SINCE) == []
