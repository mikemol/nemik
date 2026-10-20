# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W746: the depth is the longest chain of open cards waiting on open local cards."""

from nemik.climate import depth_at

SHA = "abc123"
DAY = "2026-10-%02dT00:00:00+00:00"


def _at(day: int) -> str:
    return DAY % day


def _chain_events() -> list[tuple[str, str, str, str, str, str]]:
    """List events where W3 waits on W2, W2 on W1, and W9 on a card in another repo.

    Returns:
        The events.

    """
    return [
        ("a:W1", _at(1), "status", "", "ready", SHA),
        ("a:W2", _at(1), "status", "", "blocked", SHA),
        ("a:W2", _at(1), "blocked_on", "", "W1", SHA),
        ("a:W3", _at(1), "status", "", "blocked", SHA),
        ("a:W3", _at(1), "blocked_on", "", "a:W2", SHA),
        ("a:W9", _at(1), "status", "", "blocked", SHA),
        ("a:W9", _at(1), "blocked_on", "", "b:W1", SHA),
    ]


def test_the_depth_is_the_longest_local_chain() -> None:
    """W3 -> W2 -> W1 is two cards beyond the first; a blocker in another repo adds nothing."""
    assert depth_at(_chain_events(), _at(2)) == {"a": 2.0}


def test_a_closed_blocker_no_longer_blocks() -> None:
    """When W1 is done, W2 waits on nothing open: the chain is W3 -> W2, one beyond."""
    events = [*_chain_events(), ("a:W1", _at(3), "status", "ready", "done", SHA)]
    assert depth_at(events, _at(4)) == {"a": 1.0}
    assert depth_at(events, _at(2)) == {"a": 2.0}


def test_a_cycle_terminates() -> None:
    """Two cards waiting on each other do not loop."""
    events = [
        ("a:W1", _at(1), "blocked_on", "", "W2", SHA),
        ("a:W1", _at(1), "status", "", "blocked", SHA),
        ("a:W2", _at(1), "blocked_on", "", "W1", SHA),
        ("a:W2", _at(1), "status", "", "blocked", SHA),
    ]
    assert depth_at(events, _at(2))["a"] >= 1.0
