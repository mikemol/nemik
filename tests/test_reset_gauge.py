# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1210: a declared reset is a gauge for 48 hours from its date, and then it is history."""

from nemik.pacepublish import GAUGE_RESET, metric_lines, reset_lines
from nemik.rebaselines import RESET_DATES, RESETS

TYPE_LINE = f"# TYPE {GAUGE_RESET} gauge"
MYPY = f'{GAUGE_RESET}{{repo="nemik",ratchet="mypy-baseline.json"}} 2'
RUFF = f'{GAUGE_RESET}{{repo="nemik",ratchet="ruff-baseline.json"}} 4'
DATED = "2026-10-27T11:34:22Z"  # when both resets took effect
BEFORE = "2026-10-27T11:34:21Z"
DAY_AFTER = "2026-10-28T12:00:00Z"
LAST_SECOND = "2026-10-29T11:34:21Z"  # 47 h 59 m 59 s after
EXPIRED = "2026-10-29T11:34:22Z"  # exactly 48 h after


def test_the_gauge_carries_the_new_requirement_inside_the_window() -> None:
    """A day after the reset both samples read the requirement the reset set."""
    assert reset_lines(DAY_AFTER) == [TYPE_LINE, MYPY, RUFF]


def test_the_window_opens_at_the_date_and_closes_after_48_hours() -> None:
    """Present at the date and the window's last second; absent a second before and at 48 h."""
    assert reset_lines(DATED) == [TYPE_LINE, MYPY, RUFF]
    assert reset_lines(LAST_SECOND) == [TYPE_LINE, MYPY, RUFF]
    assert reset_lines(BEFORE) == [TYPE_LINE]
    assert reset_lines(EXPIRED) == [TYPE_LINE]


def test_the_type_line_is_always_there() -> None:
    """After the window the family is empty but declared: a scrape sees it absent, not unknown."""
    assert reset_lines("2030-01-01T00:00:00Z") == [TYPE_LINE]


def test_the_published_gauges_include_the_resets_before_the_stamp() -> None:
    """metric_lines carries the family, and the file's own age stamp is still last."""
    lines = metric_lines([], DAY_AFTER)
    assert MYPY in lines
    assert lines.index(MYPY) < len(lines) - 2
    assert lines[-1].startswith("nemik_ratchet_pace_as_of ")


def test_every_declared_reset_has_a_date_and_every_date_a_reset() -> None:
    """Drift: a reset with no date would never be published, a date with no reset would be dead."""
    declared = {f"{repo}\n{ratchet}" for repo, ratchet, _, _, _ in RESETS}
    assert declared == set(RESET_DATES)
