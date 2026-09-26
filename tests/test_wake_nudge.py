"""nemik:W18 (luthen W117): age_seconds/should_nudge/due_nudges own the "is it time to nudge,
and have I already nudged recently" decision, so a caller doesn't reinvent REWAKE_S bookkeeping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from nemik.wake import age_seconds, due_nudges, should_nudge


def test_age_seconds_computes_from_iso_last_tick() -> None:
    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    then = (now - timedelta(hours=1)).isoformat()
    assert age_seconds(then, now) == 3600.0


def test_age_seconds_none_for_empty_or_unparsable() -> None:
    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    assert age_seconds("", now) is None
    assert age_seconds(None, now) is None
    assert age_seconds("not-a-date", now) is None


def test_should_nudge_true_when_never_nudged() -> None:
    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    assert should_nudge(None, now) is True


def test_should_nudge_backs_off_within_rewake_window() -> None:
    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    last_nudged = now.timestamp() - 10 * 60  # 10 min ago, default rewake is 30 min
    assert should_nudge(last_nudged, now, rewake_s=1800) is False


def test_should_nudge_true_once_rewake_window_elapses() -> None:
    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    last_nudged = now.timestamp() - 31 * 60
    assert should_nudge(last_nudged, now, rewake_s=1800) is True


def test_due_nudges_filters_state_waiting_and_backoff_then_records_seen() -> None:
    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"repo": "alpha", "state": "asleep", "waiting": [{"blocked": "x"}]},
        {"repo": "beta", "state": "awake", "waiting": [{"blocked": "y"}]},  # awake: excluded
        {"repo": "gamma", "state": "idle", "waiting": []},  # nothing waiting: excluded
        {"repo": "delta", "state": "idle", "waiting": [{"blocked": "z"}]},  # recently nudged
    ]
    seen = {"delta": now.timestamp() - 60}
    due = due_nudges(rows, seen, now)
    assert [r["repo"] for r in due] == ["alpha"]
    assert seen["alpha"] == now.timestamp()  # recorded for next call's backoff
    assert seen["delta"] == now.timestamp() - 60  # untouched: it wasn't due
