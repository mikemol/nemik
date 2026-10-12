"""nemik:W357: per week, operator asks opened and answered, and the implied wait on the operator."""

from __future__ import annotations

from datetime import UTC, datetime

from nemik.history import weekly


def _q(on_operator: list[str], other: list[str]) -> dict:
    cards = [
        {"symbol": s, "status": "blocked", "blocked_kind": "human"} for s in on_operator
    ] + [{"symbol": s, "status": "ready"} for s in other]
    return {"waypoints": cards, "residue": []}


def test_asks_entering_and_leaving_the_operator_are_counted_per_week() -> None:
    monday = datetime(2026, 10, 5, tzinfo=UTC)
    tuesday = datetime(2026, 10, 6, tzinfo=UTC)
    snaps = [
        (monday, _q(["W1", "W2"], ["W3"])),  # two asks open
        (tuesday, _q(["W2", "W3"], ["W1"])),  # W1 answered, W3 asked
    ]
    (row,) = weekly(snaps)
    assert (row["operator_asked"], row["operator_answered"]) == (3, 1)
    assert row["operator_open"] == 2
    assert row["operator_wait_days"] == 14.0  # 2 open over 1 answered a week
