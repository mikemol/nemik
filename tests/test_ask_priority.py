"""nemik:W299: an operator ask's calendar PRIORITY follows the demand it holds back."""

from __future__ import annotations

from typing import Any

from nemik.vtodo import priority, vtodos

STEPS = '[ask_priority]\n"40" = 1\n"15" = 3\n"5" = 5\n"0.01" = 7\n'


def test_the_highest_floor_reached_sets_the_priority() -> None:
    levels = [priority(s, STEPS) for s in (86.0, 40.0, 15.0, 8.7, 0.3, 0.0)]
    assert levels == [1, 1, 3, 5, 7, 9]


def test_the_packaged_steps_are_declared() -> None:
    assert priority(86.0) == 1 and priority(0.0) == 9


def _ask(ref: str, salience: float | None) -> dict[str, Any]:
    ask: dict[str, Any] = {
        "ref": ref,
        "title": "t",
        "ask": "operator: decide it",
        "category": "needs-you",
        "waiting": [],
        "same_ask": [],
        "alarms": [],
        "exdates": [],
    }
    if salience is not None:
        ask["salience"] = salience
    return ask


def test_a_vtodo_carries_priority_only_when_the_ask_is_weighed() -> None:
    weighed, plain = vtodos([_ask("a:W1", 47.0), _ask("a:W2", None)], {"a"})
    assert "PRIORITY:1" in weighed
    assert not any(line.startswith("PRIORITY") for line in plain)
