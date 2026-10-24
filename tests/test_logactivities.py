# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W947: wait records read back from the log are a repo's activities, oldest first."""

from nemik.ask import quoted
from nemik.logactivities import activities
from nemik.waitlog import activity

FIRST = 1_700_000_000_000_000_000
SECOND = FIRST + 60_000_000_000


def _record(message: str, when: str) -> str:
    """Make a VictoriaLogs line holding `message` as its _msg.

    Returns:
        The line.

    """
    return f'{{"_msg": {quoted(message)}, "_time": {quoted(when)}}}'


def _line(waiting: str, cite: str, blocker: str, at_ns: int, when: str) -> str:
    """Make the line for the wait record waitlog would send.

    Returns:
        The line.

    """
    return _record(activity(waiting, cite, 3, blocker, at_ns), when)


LATER = _line("beta", "beta:W5", "alpha:W1", SECOND, "2026-10-24T02:01:00Z")
EARLIER = _line("beta", "beta:W9", "alpha:W2", FIRST, "2026-10-24T02:00:00Z")
OTHER_REPO = _line("gamma", "gamma:W3", "alpha:W1", FIRST, "2026-10-24T02:00:00Z")


def test_a_repos_activities_come_back_oldest_first() -> None:
    """Two of beta's records given newest first are returned by published, gamma's left out."""
    found = activities([LATER, OTHER_REPO, EARLIER], "beta")
    assert [a["published"] for a in found] == [
        "2026-10-24T02:00:00Z",
        "2026-10-24T02:01:00Z",
    ]
    assert found[0]["object"] == "urn:nemik:beta/W9"
    assert found[1]["target"] == "urn:nemik:alpha/W1"
    assert found[0]["type"] == "Update"
    assert found[0]["content"] == "beta:W9 has waited 3 ticks on alpha:W2"


def test_a_line_that_is_not_a_wait_activity_is_left_out() -> None:
    """Prose, another service's JSON and a line that is no JSON are skipped, not guessed at."""
    prose = _record("beta:W5 has waited 3 ticks", "t")
    other = _record('{"event": "landing"}', "t")
    assert activities([prose, other, "not json", EARLIER], "beta") == activities(
        [EARLIER], "beta"
    )
    assert len(activities([prose, other, "not json"], "beta")) == 0
