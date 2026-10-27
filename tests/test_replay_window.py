# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1145: a window written back from now is minutes, and a replay needs a zoned instant."""

import pytest

from nemik.history import replay_text, window_minutes

QUARTER_HOUR = 45
TWO_HOURS = 120


def test_a_window_is_read_as_minutes() -> None:
    """The two spellings of a window back from now."""
    assert window_minutes("-45m") == QUARTER_HOUR
    assert window_minutes("ago:2h") == TWO_HOURS


@pytest.mark.parametrize("spec", ["abc1234", "2026-10-27", "45m"])
def test_a_revision_or_a_date_is_not_a_window(spec: str) -> None:
    """Only a window back from now has a length."""
    with pytest.raises(ValueError, match="is not a window"):
        window_minutes(spec)


def test_a_replay_instant_must_name_its_zone() -> None:
    """A time of day with no zone would read as the machine's local time."""
    with pytest.raises(ValueError, match="names no zone"):
        replay_text("-45m", "2026-10-27T03:13:00", [], {})


def test_a_replay_of_no_repos_predicts_nothing_and_nets_nothing() -> None:
    """With no repo there is no history; the replay still runs and reads a quiet window."""
    line = replay_text("-45m", "2026-10-27T03:13:00Z", [], {})
    assert line == "replay: predicted +0.0, realized +0, shortfall +0.0"
