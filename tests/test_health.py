# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W317: repo health is the worst of its declared signals, with a reason per crossing."""

from __future__ import annotations

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.health import health, thresholds

LIMITS = {
    "blocked_share": (0.5, 0.8),
    "oldest_block_ticks": (16.0, 48.0),
    "asks_owed": (1.0, 5.0),
}


def _repo(states: list[str], ticks: int = 0) -> Graph:
    g = Graph()
    for i, state in enumerate(states):
        node = waypoint_uri("a", f"W{i + 1}")
        g.add((node, OSLC_CM.state, STATE[state]))
        if state == "blocked":
            g.add((node, NEMIK.ticksBlocked, Literal(ticks)))
    return g


def test_declared_thresholds_are_read_for_each_signal() -> None:
    """Declared thresholds are read for each signal."""
    declared = thresholds(
        "[health]\nblocked_share = [0.4, 0.9]\noldest_block_ticks = [8, 20]\nasks_owed = [2, 4]\n"
    )
    assert declared == {
        "blocked_share": (0.4, 0.9),
        "oldest_block_ticks": (8.0, 20.0),
        "asks_owed": (2.0, 4.0),
    }
    assert set(thresholds()) == set(LIMITS)  # the packaged table declares all three


def test_a_repo_is_green_until_a_signal_crosses_its_floor() -> None:
    """A repo is green until a signal crosses its floor."""
    green = health(_repo(["ready", "ready", "blocked"]), "a", LIMITS)
    assert green.status == "green"
    assert green.reasons == []


def test_the_worst_signal_decides_and_each_crossing_is_named() -> None:
    """2 of 3 blocked is a share of 0.667 (amber); a card blocked 50 ticks is red.

    The worst signal decides the status (red), and each crossing is named as a reason.
    """
    found = health(_repo(["ready", "blocked", "blocked"], ticks=50), "a", LIMITS)
    assert found.status == "red"
    assert found.blocked_share == 0.667
    assert found.oldest_block_ticks == 50
    assert len(found.reasons) == 2
    assert any("oldest_block_ticks" in r and "red" in r for r in found.reasons)
    assert any("blocked_share" in r and "amber" in r for r in found.reasons)


def test_a_done_card_and_another_repos_card_do_not_count() -> None:
    """A done card and another repos card do not count."""
    g = _repo(["blocked", "done"], ticks=60)
    other = waypoint_uri("b", "W1")
    g.add((other, OSLC_CM.state, STATE["ready"]))
    assert health(g, "a", LIMITS).blocked_share == 1.0
    assert health(g, "b", LIMITS).status == "green"
