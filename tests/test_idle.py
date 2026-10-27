# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W577: an idle loop with nothing workable is a Warning; one with a ready card is not."""

import json
import tempfile
from pathlib import Path

from nemik.check import survey
from nemik.idle import DEFAULT_TICKS, declared, idle_run


def _write(
    root: Path, status: str, outcomes: list[str], *, agent: bool = False
) -> None:
    """Write a one-card repo named r with a ledger of tick lines.

    Args:
        root: The directory holding repos.
        status: The one card's status.
        outcomes: The outcome of each tick line, oldest first.
        agent: Whether a blocked card waits on another repo's card and not on the operator.

    """
    wait = "other:W9" if agent else "operator: decide x"
    kind = "agent" if agent else "human"
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": status,
        "blocked_on": [wait] if status == "blocked" else [],
        "blocked_kind": kind if status == "blocked" else None,
        "next_bounded_step": "x",
    }
    state = {
        "version": 1,
        "project_root": "/r",
        "counter": 1,
        "residue": [],
        "waypoints": [card],
    }
    claude = root / "r" / ".claude"
    claude.mkdir(parents=True)
    (claude / "paths-forward.json").write_text(json.dumps(state))
    lines = [
        f'2026-10-16T{n // 60:02d}:{n % 60:02d}:00Z  tick  W1 {outcome}  sweep  "no change"'
        for n, outcome in enumerate(outcomes)
    ]
    (claude / "paths-forward.ledger").write_text("\n".join(lines) + "\n")


def _idle_warnings(root: Path) -> list[str]:
    """Collect the idle-loop warnings the survey gives repo r.

    Args:
        root: The directory holding repos.

    Returns:
        The warning texts.

    """
    return [
        msg
        for _, _, findings in survey(root)
        for sev, sym, msg in findings
        if sev == "Warning" and sym == "--" and "advanced nothing" in msg
    ]


def test_the_run_counts_only_the_trailing_idle_ticks() -> None:
    """An advance in the middle resets the count; only the newest run matters."""
    trailing = ["idle", "idle"]
    assert idle_run(["idle", "advanced", *trailing], ["idle"]) == len(trailing)
    assert idle_run(["advanced"], ["idle"]) == 0


def test_the_declared_run_is_data() -> None:
    """The count and the idle outcomes come from rank-weights.toml, with defaults when absent."""
    ticks, outcomes = declared("[idle]\nticks = 4\noutcomes = ['idle', 'quiet']\n")
    assert str(ticks) == "4"
    assert outcomes == ["idle", "quiet"]
    assert declared("x = 1\n") == (DEFAULT_TICKS, ["idle"])


def test_a_long_idle_run_with_nothing_workable_is_a_warning() -> None:
    """Sixteen idle ticks over a blocked-only queue says to disarm or name the wait."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(Path(tmp), "blocked", ["idle"] * 16)
        found = _idle_warnings(Path(tmp))
    assert len(found) == 1
    assert "disarm the loop" in found[0]


def test_a_queue_blocked_only_on_agents_is_told_to_nudge_not_to_disarm() -> None:
    """amr-skills disarmed on this warning with its cards waiting on agents; the prompt nudges."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(Path(tmp), "blocked", ["idle"] * 16, agent=True)
        found = _idle_warnings(Path(tmp))
    assert len(found) == 1
    assert "do not disarm" in found[0]
    assert "other:W9" in found[0]
    assert "disarm the loop" not in found[0]


def test_a_ready_card_or_a_short_run_is_not() -> None:
    """Work to do, or fewer idle ticks than the declared run, draws no warning."""
    with tempfile.TemporaryDirectory() as tmp:
        _write(Path(tmp), "ready", ["idle"] * 16)
        assert _idle_warnings(Path(tmp)) == []
    with tempfile.TemporaryDirectory() as tmp:
        _write(Path(tmp), "blocked", ["idle"] * 15)
        assert _idle_warnings(Path(tmp)) == []
