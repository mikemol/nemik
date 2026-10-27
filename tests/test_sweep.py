# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1152: a sweep alerts on planted misses in both directions, and counts its alerts."""

from nemik.netforecast import sweep_alerts, sweep_lines

HOUR = 60
PAST = 10
CAP = 10  # the most lines a hook may print
DAILY = [-48, -48, -48]  # predicted -2 an hour
STEADY = [-2, -1, -3, -2, -2, -1, -3, -2, -2, -2]  # ten steady windows


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
    assert sweep_lines(judged, [], HOUR, 7, 10) == [
        "swept 1 windows of 60 minutes over 7 days: alerted 0 of 1"
    ]


def test_windows_before_the_baseline_has_history_are_not_judged() -> None:
    """The first ten windows only teach the baseline; fewer than that judge none."""
    assert sweep_alerts(DAILY, HOUR, STEADY, PAST) == (0, [])


def test_the_sweep_lines_name_each_alert_and_fold_the_rest_into_a_tail() -> None:
    """The head is the count; each alerted window follows; the cap holds."""
    alerts = [(f"t{n:02d}", "fleet wandering") for n in range(12)]
    lines = sweep_lines(40, alerts, HOUR, 7, CAP)
    assert lines[0] == "swept 40 windows of 60 minutes over 7 days: alerted 12 of 40"
    assert lines[1] == "  t00: fleet wandering"
    assert len(lines) == CAP
    assert lines[-1] == "  +4 more alerted"
