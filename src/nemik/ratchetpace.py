# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W987: whether a ratchet is paying down fast enough, over the landed commits of its repo.

The operator asked for a ratchet paydown rate requirement with teeth (host 695f3e0a line 93406).
A ratchet's series is its value after each landed commit, oldest first. The unit is the landed
commit, not the calendar week (the design github:W42 accepted): a quiet week asks nothing and a
busy one asks more. The observed fall is the drop over the last `window` landings. The required
fall is seeded from the ratchet's own earlier windows, the mean fall per window rounded up, never
below one while the value is above zero (a nonzero ratchet is a priority marker, operator
2026-10-24, line 92679), and it only rises: the caller keeps the largest requirement it has
stated and passes it back as `prior`. Integer arithmetic only, and no import, so the Codon census
compiles it.
"""

WINDOW = 10  # landed commits in one window
OK = "ok"
BEHIND = "behind"


def window_fall(values: list[int], window: int) -> int:
    """Measure how far a ratchet fell over its last window of landings.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings the window spans.

    Returns:
        The value `window` landings ago less the value now (positive means paid down); 0 when the
        series is shorter than the window.

    """
    if window < 1 or len(values) <= window:
        return 0
    return values[-1 - window] - values[-1]


def seed(values: list[int], window: int) -> int:
    """Measure the mean fall of the ratchet's windows before the last one.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings one window spans.

    Returns:
        The mean fall per whole window of the history that ends where the last window starts,
        rounded up; 0 when that history holds no whole window.

    """
    history = values[: len(values) - window] if len(values) > window else []
    steps = (len(history) - 1) // window if history else 0
    if steps < 1:
        return 0
    total = history[0] - history[steps * window]
    return max(0, -(-total // steps))


def required(values: list[int], window: int, prior: int) -> int:
    """State the fall the ratchet owes over one window.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings one window spans.
        prior: The largest requirement stated before; the new one never falls below it.

    Returns:
        The larger of the prior requirement, the seed, and one while the value is above zero, but
        never more than the value now: a ratchet cannot fall further than zero, so it is never
        asked for more than it holds (panflute required 6 against a value of 1, W1105); a ratchet
        at zero owes nothing.

    """
    now = values[-1] if values else 0
    if now <= 0:
        return 0
    return min(max(prior, seed(values, window), 1), now)


def verdict(values: list[int], window: int, prior: int) -> tuple[str, int, int]:
    """Judge a ratchet: behind when its observed fall is below what it owes.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings one window spans.
        prior: The largest requirement stated before.

    Returns:
        (`behind` or `ok`, the observed fall, the required fall). A series no longer than one window
        is judged against the floor alone, so a nonzero ratchet that has not yet fallen is behind.

    """
    owed = required(values, window, prior)
    fell = window_fall(values, window)
    return (BEHIND if fell < owed else OK), fell, owed
