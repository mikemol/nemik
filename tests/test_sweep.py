# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1152, W1153: a sweep alerts on planted misses both ways, and counts its alerts."""

from nemik.netforecast import sweep_alerts, sweep_report, trailing_alerts

HOUR = 60
PAST = 10
CAP = 10  # the most lines a hook may print
SPAN_TEXT = "60 minutes over 7 days"
DAILY = [-48, -48, -48]  # predicted -2 an hour
STEADY = [-2, -1, -3, -2, -2, -1, -3, -2, -2, -2]  # ten steady windows
SPAN = 3  # windows a trailing prediction is the mean of
BEFORE = 3  # earlier windows a trailing baseline is learned from
FLAT = [-2] * (SPAN + BEFORE)  # six windows that netted what the trailing mean says


def test_a_window_far_under_its_prediction_alerts_fleet_wandering() -> None:
    """A planted deficit beyond the learned spread: the fleet did worse than predicted."""
    judged, alerts = sweep_alerts(DAILY, HOUR, [*STEADY, -9], PAST)
    assert judged == 1
    assert alerts == [(PAST, "fleet wandering")]


def test_a_window_far_over_its_prediction_alerts_model_wrong() -> None:
    """A planted surplus beyond the spread: the model expected worse than happened."""
    judged, alerts = sweep_alerts(DAILY, HOUR, [*STEADY, 5], PAST)
    assert judged == 1
    assert alerts == [(PAST, "model wrong")]


def test_a_window_inside_the_spread_stays_silent_and_is_counted_as_zero() -> None:
    """Within the usual miss: no alert, and the zero is a count of one window judged."""
    judged, alerts = sweep_alerts(DAILY, HOUR, [*STEADY, -3], PAST)
    assert (judged, alerts) == (1, [])
    assert sweep_report(judged, [], SPAN_TEXT, CAP) == [
        "swept 1 windows of 60 minutes over 7 days: alerted 0 of 1"
    ]


def test_windows_before_the_baseline_has_history_are_not_judged() -> None:
    """The first ten windows only teach the baseline; fewer than that judge none."""
    assert sweep_alerts(DAILY, HOUR, STEADY, PAST) == (0, [])


def test_the_sweep_report_counts_directions_and_folds_the_rest_into_a_tail() -> None:
    """The head is the count with its directions; each alerted window follows; the cap holds."""
    alerts = [(f"t{n:02d}", "fleet wandering") for n in range(10)]
    alerts += [("t10", "model wrong"), ("t11", "model wrong")]
    lines = sweep_report(40, alerts, SPAN_TEXT, CAP, "trailing prediction: ")
    assert lines[0] == (
        "trailing prediction: swept 40 windows of 60 minutes over 7 days: "
        "alerted 12 of 40 (fleet wandering 10, model wrong 2)"
    )
    assert lines[1] == "  t00: fleet wandering"
    assert len(lines) == CAP
    assert lines[-1] == "  +4 more alerted"


def test_a_trailing_prediction_alerts_both_ways_and_stays_silent_inside() -> None:
    """The same three planted windows, each predicted from the windows just before it."""
    assert trailing_alerts([*FLAT, -9], SPAN, BEFORE) == (1, [(6, "fleet wandering")])
    assert trailing_alerts([*FLAT, 5], SPAN, BEFORE) == (1, [(6, "model wrong")])
    assert trailing_alerts([*FLAT, -2], SPAN, BEFORE) == (1, [])


def test_a_trailing_prediction_alerts_at_a_shift_and_then_follows_it() -> None:
    """The fleet drops to a new level: the window of the shift alerts, the ones after are judged."""
    moved = [-2] * 6 + [-20] * 8
    judged, alerts = trailing_alerts(moved, SPAN, BEFORE)
    assert judged == len(moved) - SPAN - BEFORE
    assert alerts == [(6, "fleet wandering")]


def test_a_trailing_sweep_with_too_few_windows_judges_none() -> None:
    """Fewer windows than the span plus the baseline's: a count of zero, not a guess."""
    assert trailing_alerts(FLAT, SPAN, BEFORE) == (0, [])
