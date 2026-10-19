# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W683: consecutive tick rolls at advanced 0 are a stalled-session signal."""

from nemik.rolls import NOT_A_ROLL, advanced, idle_run, stalled

LANDED = 3
RUN = 2
IDLE = "closed [rolled; advanced 0]"
BUSY = f"closed [rolled; advanced {LANDED}]"
PLAIN = "closed by hand"


def test_the_count_is_read_from_the_roll_text() -> None:
    """A roll note gives its N, anything else is not a roll."""
    assert advanced(BUSY) == LANDED
    assert advanced(IDLE) == 0
    assert advanced(PLAIN) == NOT_A_ROLL


def test_the_run_counts_only_the_newest_idle_rolls() -> None:
    """An older idle roll behind a busy one does not count."""
    assert idle_run([IDLE, BUSY, IDLE, IDLE]) == RUN
    assert idle_run([IDLE, IDLE, BUSY]) == 0
    assert idle_run([]) == 0


def test_a_plain_close_ends_the_run() -> None:
    """A tick that was not a roll breaks the run."""
    assert idle_run([IDLE, PLAIN, IDLE]) == 1


def test_stalled_needs_the_limit_and_a_ready_card() -> None:
    """Two idle rolls with a ready card stall; with nothing ready they do not."""
    assert stalled([IDLE, IDLE], ready=1, limit=2)
    assert not stalled([IDLE], ready=1, limit=2)
    assert not stalled([IDLE, IDLE], ready=0, limit=2)
