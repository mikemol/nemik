# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W318: planned versus actual since a baseline revision."""

from __future__ import annotations

from pathlib import Path

from nemik.history import baseline_spec, variance


def _q(cards: dict[str, tuple[str, str]], residue: tuple[str, ...] = ()) -> dict:
    return {
        "waypoints": [
            {"symbol": s, "status": st, "minted_during": during}
            for s, (st, during) in cards.items()
        ],
        "residue": [{"symbol": s} for s in residue],
    }


def test_the_plan_is_what_was_open_at_the_baseline_and_the_rest_is_added() -> None:
    base = _q(
        {"W1": ("ready", "tick"), "W2": ("blocked", "tick"), "W3": ("done", "tick")}
    )
    now = _q(
        {
            "W1": ("done", "tick"),
            "W2": ("blocked", "tick"),
            "W3": ("done", "tick"),
            "W5": ("ready", "interrupt"),
            "W6": ("ready", "tick"),
        },
        residue=("W4",),
    )
    v = variance(base, now)
    assert v["planned"] == 2  # W3 was already done at the baseline
    assert v["closed"] == ["W1"] and v["still_open"] == ["W2"] and v["dropped"] == []
    assert v["done_share"] == 0.5
    # W4 was minted and dropped after the baseline: added, with no record of how
    assert v["added"] == {"interrupt": ["W5"], "tick": ["W6"], "unrecorded": ["W4"]}


def test_a_planned_card_dropped_since_counts_as_dropped() -> None:
    base = _q({"W1": ("ready", "tick")})
    now = _q({}, residue=("W1",))
    v = variance(base, now)
    assert v["dropped"] == ["W1"] and v["closed"] == [] and v["still_open"] == []


def test_shape_drift_counts_edges_and_the_planned_cards_retitled_or_rewired() -> None:
    # nemik:W349: W1 and W2 planned; W1 gains an edge to the new W3, W2 is retitled.
    from nemik.history import shape_drift

    base = {
        "waypoints": [
            {"symbol": "W1", "status": "ready", "title": "one", "enables": []},
            {"symbol": "W2", "status": "ready", "title": "two", "enables": []},
        ],
        "residue": [],
    }
    now = {
        "waypoints": [
            {"symbol": "W1", "status": "ready", "title": "one", "enables": ["W3"]},
            {"symbol": "W2", "status": "ready", "title": "two, narrower"},
            {"symbol": "W3", "status": "ready", "title": "three"},
        ],
        "residue": [],
    }
    sh = shape_drift(base, now)
    assert (sh["edges_added"], sh["edges_removed"]) == (1, 0)
    assert sh["retitled"] == ["W2"] and sh["rewired"] == ["W1"]
    assert sh["touched_share"] == 1.0


def test_the_baseline_is_given_or_declared_in_the_repo(tmp_path: Path) -> None:
    assert baseline_spec(tmp_path, None) is None
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "baseline").write_text("2026-10-01  sprint start\n")
    assert baseline_spec(tmp_path, None) == "2026-10-01"
    assert baseline_spec(tmp_path, "abc123") == "abc123"
