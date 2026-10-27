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


def sweep_alerts(
    daily_nets: list[int], minutes: int, nets: list[int], past: int
) -> tuple[int, list[tuple[int, str]]]:
    """Judge a run of windows, each against the windows just before it (nemik:W1152).

    Args:
        daily_nets: The net of each of the days before the first window.
        minutes: The windows' length in minutes.
        nets: The net of each window, oldest first.
        past: How many windows before one it learns its baseline from.

    Returns:
        (the windows judged, each alerted one's index with its direction): a window is judged
        once `past` windows precede it; 'fleet wandering' when it did worse than predicted and
        'model wrong' when it did better. The count of alerts may be zero, and is then reported
        as zero, so a quiet alert is visibly quiet.

    """
    predicted = predicted_net(daily_nets, minutes)
    alerts: list[tuple[int, str]] = []
    for at in range(past, len(nets)):
        earlier = [shortfall(predicted, net) for net in nets[at - past : at]]
        if alert_for(predicted, nets[at], earlier):
            worse = shortfall(predicted, nets[at]) > 0
            alerts.append((at, "fleet wandering" if worse else "model wrong"))
    return max(0, len(nets) - past), alerts


def sweep_report(
    judged: int,
    alerts: list[tuple[str, str]],
    span: str,
    limit: int,
    label: str = "",
) -> list[str]:
    """Write a sweep's count, its directions and its alerted windows (nemik:W1152, W1153).

    Args:
        judged: How many windows were judged.
        alerts: Each alerted window's label (its end time) and direction, oldest first.
        span: What was swept, as '45 minutes over 7 days'.
        limit: The most lines to give.
        label: What kind of prediction judged them, put before the count.

    Returns:
        'swept n windows of SPAN: alerted k of n (direction count, ...)', then one line per
        alerted window, and a tail line for those that did not fit. The count is printed when it
        is zero, and the parenthesis then is left off.

    """
    ways = sorted({way for _, way in alerts})
    tally = ", ".join(f"{way} {sum(1 for _, w in alerts if w == way)}" for way in ways)
    head = (
        f"{label}swept {judged} windows of {span}: alerted {len(alerts)} of {judged}"
        + (f" ({tally})" if alerts else "")
    )
    room = limit - 1
    shown = alerts if len(alerts) <= room else alerts[: room - 1]
    lines = [head, *(f"  {when}: {way}" for when, way in shown)]
    if len(shown) < len(alerts):
        lines.append(f"  +{len(alerts) - len(shown)} more alerted")
    return lines


def trailing_alerts(
    nets: list[int], span: int, past: int
) -> tuple[int, list[tuple[int, str]]]:
    """Judge a run of windows, each predicted from the `span` windows just before it (W1153).

    A window's prediction is the mean net of the `span` windows before it (a week of them, for
    windows that divide the day), so it looks ahead of nothing and follows the fleet as the
    week goes, where sweep_alerts predicts every window from the days before the first.

    Args:
        nets: The net of each window, oldest first.
        span: How many windows before one its prediction is the mean of.
        past: How many earlier windows' misses its baseline is learned from; each of those is
            judged against its own trailing prediction, not this window's.

    Returns:
        (the windows judged, each alerted one's index with its direction), as sweep_alerts does.
        A window is judged once `span` plus `past` windows precede it; the count may be zero.

    """
    first = span + past
    alerts: list[tuple[int, str]] = []
    for at in range(first, len(nets)):
        predicted = sum(nets[at - span : at]) / span
        earlier = [
            shortfall(sum(nets[j - span : j]) / span, nets[j])
            for j in range(at - past, at)
        ]
        if alert_for(predicted, nets[at], earlier):
            worse = shortfall(predicted, nets[at]) > 0
            alerts.append((at, "fleet wandering" if worse else "model wrong"))
    return max(0, len(nets) - first), alerts


def replay_row(
    daily_nets: list[int], minutes: int, past_nets: list[int], realized: int
) -> str:
    """Set a replayed window's prediction beside what happened, and say if they part (W1145).

    The prediction comes from the days before every window it is judged against, so it looks
    ahead of none of them; the baseline is learned from `past_nets`, the earlier windows.

    Args:
        daily_nets: The net of each of the days before the earliest past window.
        minutes: The window's length in minutes.
        past_nets: The net of each earlier window of that length.
        realized: The net the replayed window actually had.

    Returns:
        A line with the prediction, the realized net and the shortfall, and a second line with
        the alert when there is one. ValueError from the prediction or the baseline propagates:
        too little history is not a quiet window.

    """
    predicted = predicted_net(daily_nets, minutes)
    gap = shortfall(predicted, realized)
    line = f"replay: predicted {predicted:+.1f}, realized {realized:+d}, shortfall {gap:+.1f}"
    said = alert_for(predicted, realized, [shortfall(predicted, n) for n in past_nets])
    return f"{line}\n{said}" if said else line


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
    limit = baseline_of([abs(past) for past in past_shortfalls])
    if abs(gap) <= limit:
        return ""
    verdict = (
        "the fleet did worse than predicted: look why"
        if gap > 0
        else "the model expected worse than happened: fix it"
    )
    return (
        f"misprediction: net {realized:+d} against a predicted {predicted:+.1f}, "
        f"off by {abs(gap):.1f} over the usual {limit:.1f}; {verdict}"
    )
