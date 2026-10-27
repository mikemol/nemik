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
MIN_WINDOWS = 3  # whole earlier windows a trend needs before it seeds a requirement
OK = "ok"
BEHIND = "behind"
NO_HORIZON = -1  # nothing fell over the window, so no landings-to-zero can be stated


def window_fall(values: list[int], window: int) -> int:
    """Measure how far a ratchet fell over its last window of landings.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings the window spans.

    Returns:
        The value `window` landings ago less the value now (positive means paid down). A series
        no longer than the window falls over the history it has: its first value less its last,
        so a ratchet that was re-baselined a few landings ago and has paid down since is not read
        as one that never fell (linux-sources' letter-quotes, 18 to 2 over nine samples, read
        observed 0 and behind, W1155); an empty series, or no window, gives 0.

    """
    if window < 1 or not values:
        return 0
    if len(values) <= window:
        return values[0] - values[-1]
    return values[-1 - window] - values[-1]


def steps_seen(values: list[int], window: int) -> int:
    """Count the landings the observed fall spans.

    Returns:
        The window, or fewer when the series is shorter: one fewer than its samples, never below
        zero.

    """
    return max(0, min(window, len(values) - 1))


def seed(values: list[int], window: int) -> int:
    """Measure the mean fall of the ratchet's windows before the last one.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings one window spans.

    Returns:
        The median of the falls of the whole windows of the history that ends where the last
        window starts; 0 when that history holds fewer than MIN_WINDOWS whole windows. A trend
        needs a few windows and a middle, not one window and its mean: nemik's mypy series, 22
        samples after a declared re-baseline, held exactly one whole earlier window, whose fall
        of 109 was W1124's single 104-finding paydown, and that burst became a requirement of 109
        a window that only rises (W1158).

    """
    history = values[: len(values) - window] if len(values) > window else []
    steps = (len(history) - 1) // window if history else 0
    if steps < MIN_WINDOWS:
        return 0
    falls = sorted(
        history[at * window] - history[(at + 1) * window] for at in range(steps)
    )
    return max(0, falls[steps // 2])


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


def horizon(values: list[int], window: int) -> int:
    """Count the landings a ratchet needs to reach zero at the pace it last fell.

    Not behind is not falling: ten findings a landing off 2,715 is 272 landings (W1112).

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings the window spans.

    Returns:
        The value now divided by the fall per landing over the last window (or over the landings
        a shorter series has seen), rounded up; 0 when the value is zero; NO_HORIZON when nothing
        fell.

    """
    now = values[-1] if values else 0
    if now <= 0:
        return 0
    fell = window_fall(values, window)
    if fell <= 0:
        return NO_HORIZON
    return -(-now * steps_seen(values, window) // fell)


def verdict(values: list[int], window: int, prior: int) -> tuple[str, int, int]:
    """Judge a ratchet: behind when its observed fall is below what it owes.

    Args:
        values: The ratchet's value after each landed commit, oldest first.
        window: How many landings one window spans.
        prior: The largest requirement stated before.

    Returns:
        (`behind` or `ok`, the observed fall, the required fall). A series no longer than one window
        is judged on the fall it has seen against the floor, so a nonzero ratchet that has not yet
        fallen is behind and one that has fallen the floor already is not.

    """
    owed = required(values, window, prior)
    fell = window_fall(values, window)
    return (BEHIND if fell < owed else OK), fell, owed
