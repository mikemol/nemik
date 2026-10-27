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
