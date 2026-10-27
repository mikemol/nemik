# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1144: the net a window is predicted to have, from the days before it.

The operator's ruling (host 695f3e0a line 70715, 2026-10-16): a backlog state, if there is one, is
predictive and not controlling, and a prediction that does not meet reality is an alert. A
window's net is the cards closed plus dropped less the cards added (nemik-history --compact). The
prediction here is the plainest honest one: the mean of the daily nets of the days before the
window, scaled to the window's length. It controls nothing; W1145 sets it beside what happened
and W1146 says when the two part.
"""

MINUTES_PER_DAY = 24 * 60
MIN_PAST = 3  # windows needed before a baseline of shortfalls is learned
BASELINE_PERCENT = 90  # the share of past shortfalls the baseline sits above


def predicted_net(daily_nets: list[int], minutes: int) -> float:
    """Predict a window's net from the daily nets that came before it.

    Args:
        daily_nets: The net of each of the days before the window (closed plus dropped less
            added), one per day.
        minutes: The window's length in minutes.

    Returns:
        The mean daily net scaled to `minutes`; negative when the days before added more than they
        closed.

    Raises:
        ValueError: When there are no days to predict from, or the window has no length: an
            unknown prediction is never read as a prediction of zero.

    """
    if not daily_nets:
        message = "no days to predict from"
        raise ValueError(message)
    if minutes <= 0:
        message = "a window has a length"
        raise ValueError(message)
    return sum(daily_nets) / len(daily_nets) * minutes / MINUTES_PER_DAY


def shortfall(predicted: float, realized: int) -> float:
    """Measure how far a window's net fell short of its prediction (nemik:W1146).

    Returns:
        The prediction less the realized net: positive when the window did worse than predicted.

    """
    return predicted - realized


def baseline_of(past_shortfalls: list[float]) -> float:
    """Learn what a normal shortfall is from the windows already seen.

    Args:
        past_shortfalls: The shortfall of each past window.

    Returns:
        The shortfall that BASELINE_PERCENT of the past windows did not exceed (nearest rank); the
        baseline is learned from the series, never declared.

    Raises:
        ValueError: When fewer than MIN_PAST windows are known: with too little history the
            baseline is unknown, and an unknown baseline must not read as a quiet one.

    """
    if len(past_shortfalls) < MIN_PAST:
        message = "too few past windows to learn a baseline"
        raise ValueError(message)
    ordered = sorted(past_shortfalls)
    rank = -(-len(ordered) * BASELINE_PERCENT // 100)  # the ceiling, without a float
    return ordered[rank - 1]


def alert_for(predicted: float, realized: int, past_shortfalls: list[float]) -> str:
    """Say whether a window's net parted from its prediction beyond what is normal (W1146).

    The operator's ruling (host 695f3e0a line 70715): a prediction that does not meet reality is
    an alert. This only says so, in words; it controls nothing and gates nothing.

    Args:
        predicted: The window's predicted net (predicted_net).
        realized: The net the window actually had.
        past_shortfalls: The shortfall of each past window (shortfall).

    Returns:
        A one-line alert when the shortfall exceeds the learned baseline, else an empty string.
        Too little history to learn the baseline raises ValueError, as baseline_of does.

    """
    gap = shortfall(predicted, realized)
    limit = baseline_of(past_shortfalls)
    if gap <= limit:
        return ""
    return (
        f"misprediction: net {realized:+d} against a predicted {predicted:+.1f}, "
        f"a shortfall of {gap:.1f} over the usual {limit:.1f}"
    )
