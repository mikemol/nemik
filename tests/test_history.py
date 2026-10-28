# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W267: nemik-history diffs a repo's committed queue between two revisions."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from nemik.history import (
    QueueDoc,
    backfill,
    diff,
    ledger_lines_since,
    longest_gap_hours,
    main,
    queue_at,
    queues_text_at,
    resolve,
    slim,
    snapshots,
    time_in_state,
    weekly,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# The slim-queue cache of this run is a directory of its own, not the user's.
os.environ["NEMIK_CACHE_DIR"] = tempfile.mkdtemp(prefix="nemik-history-cache-")


def test_the_commit_history_of_a_queue_is_a_list_of_events(tmp_path: Path) -> None:
    """nemik:W744: the first commit mints W1, the second closes it and mints W2."""
    repo, first = _two_commits(tmp_path)
    got = backfill("a", repo)
    changes = [(station, field, was, now) for station, _, field, was, now, _ in got]
    assert changes == [
        ("a:W1", "card", "", "minted"),
        ("a:W1", "status", "", "ready"),
        ("a:W1", "status", "ready", "done"),
        ("a:W2", "card", "", "minted"),
        ("a:W2", "status", "", "ready"),
    ]
    assert got[0][5] == first


def test_a_start_date_compares_the_first_commit_after_it_with_the_state_before(
    tmp_path: Path,
) -> None:
    """nemik:W744: from between the two commits, W1 is not minted again, only changed."""
    repo, _ = _two_commits(tmp_path)
    got = backfill("a", repo, "2026-10-03")
    changes = [(station, field, was, now) for station, _, field, was, now, _ in got]
    assert changes == [
        ("a:W1", "status", "ready", "done"),
        ("a:W2", "card", "", "minted"),
        ("a:W2", "status", "", "ready"),
    ]


def test_a_null_or_empty_field_in_a_committed_queue_reads_as_empty(
    tmp_path: Path,
) -> None:
    """nemik:W744: real queues store null for an unset blocked_kind; it must not raise."""
    repo, _ = _two_commits(tmp_path)
    card = _wp("W3", "ready", blocked_kind=None, blocked_on=[])
    _commit(repo, {"waypoints": [card], "residue": []}, "2026-10-06T12:00:00Z")
    third = [event for event in backfill("a", repo) if event[0] == "a:W3"]
    assert [event[2:5] for event in third] == [
        ("card", "", "minted"),
        ("status", "", "ready"),
    ]


def test_ledger_lines_are_counted_from_a_stamp(tmp_path: Path) -> None:
    """nemik:W741: only the lines stamped at or after the cutoff count; no ledger is none."""
    ledger = tmp_path / "x.ledger"
    ledger.write_text(
        "2026-10-01T00:00:00Z  tick  W1\n"
        "2026-10-05T12:00:00Z  tick  W2\n"
        "2026-10-06T00:00:00Z  tick  W3\n",
        encoding="utf-8",
    )
    kept = len(ledger.read_text(encoding="utf-8").splitlines()) - 1
    assert ledger_lines_since(ledger, "2026-10-05T00:00:00Z") == kept
    assert not ledger_lines_since(ledger, "2026-11-01T00:00:00Z")
    assert not ledger_lines_since(tmp_path / "missing.ledger", "2026-10-01T00:00:00Z")


def test_the_longest_gap_between_commits_is_in_hours() -> None:
    """nemik:W739: three commits 2 h and 30 h apart have a longest gap of 30 hours."""
    first = datetime(2026, 10, 1, 8, tzinfo=UTC)
    stamps = [
        first,
        datetime(2026, 10, 1, 10, tzinfo=UTC),
        datetime(2026, 10, 2, 16, tzinfo=UTC),
    ]
    expected = 30.0
    assert abs(longest_gap_hours(stamps) - expected) < 1
    assert not longest_gap_hours(stamps[:1])
    assert not longest_gap_hours([])


def test_slim_drops_what_no_history_reader_uses_and_keeps_its_answers() -> None:
    """nemik:W731: evidence and titles go; the diff of two queues is the same on the slim ones."""
    old: QueueDoc = {
        "waypoints": [{"symbol": "W1", "status": "ready", "evidence": "x" * 500}],
        "residue": [],
    }
    new: QueueDoc = {
        "waypoints": [
            {"symbol": "W1", "status": "done", "title": "t", "enables": ["W2"]},
            {"symbol": "W2", "status": "blocked", "blocked_on": ["mtools:W9"]},
        ],
        "residue": [{"symbol": "W0", "reason": "r" * 500}],
    }
    assert "x" * 500 not in str(slim(old))
    assert "'evidence_len': '500'" in str(slim(old))
    assert "title" not in str(slim(new))
    assert "r" * 500 not in str(slim(new))
    assert diff(slim(old), slim(new)) == diff(old, new)


def test_the_queue_at_many_revisions_is_read_by_one_git_process(tmp_path: Path) -> None:
    """nemik:W725: the batch is one `git cat-file`, however many commits it reads."""
    repo, first = _two_commits(tmp_path)
    trace = tmp_path / "trace.txt"
    os.environ["GIT_TRACE"] = str(trace)
    try:
        texts = queues_text_at(repo, [first, "HEAD"])
    finally:
        del os.environ["GIT_TRACE"]
    assert all(texts)
    assert texts[0] != texts[1]
    assert trace.read_text().count("built-in: git cat-file") == 1
    assert queues_text_at(repo, []) == []


def test_a_second_snapshots_call_reads_no_queue_from_git(tmp_path: Path) -> None:
    """nemik:W729: blobs already seen are kept by id, so only the blob-id check is a git read."""
    repo, _ = _two_commits(tmp_path)
    trace = tmp_path / "trace.txt"
    os.environ["NEMIK_CACHE_DIR"] = str(tmp_path / "cache")
    try:
        first = snapshots(repo)
        os.environ["GIT_TRACE"] = str(trace)
        try:
            second = snapshots(repo)
        finally:
            del os.environ["GIT_TRACE"]
    finally:
        del os.environ["NEMIK_CACHE_DIR"]
    assert first
    assert first == second
    assert trace.read_text().count("built-in: git cat-file") == 1


def _wp(symbol: str, status: str = "ready", **more: object) -> dict:
    return {"symbol": symbol, "status": status, **more}


def test_diff_names_every_class_of_change() -> None:
    old = {
        "waypoints": [
            _wp("W1"),
            _wp("W2"),
            _wp("W3", "blocked", blocked_on=["W1"]),
            _wp("W4"),
        ],
        "residue": [],
    }
    new = {
        "waypoints": [
            _wp("W1", "done"),
            _wp("W2", "working"),
            _wp("W3", "blocked", blocked_on=["W1", "mtools:W5"]),
            _wp("W6", enables=["W2"]),
        ],
        "residue": [{"symbol": "W4", "reason": "no"}],
    }
    d = diff(old, new)
    assert d.minted == ["W6"]
    assert d.closed == ["W1"]
    assert d.dropped == ["W4"]
    assert d.flips == [("W2", "ready", "working")]  # the flip into done is `closed`
    assert d.edges_added == [
        ("enables", "W6", "W2"),
        ("waits", "W3", "mtools:W5"),
    ]
    assert d.edges_removed == []
    assert d.new_cross_blocks == [("W3", "mtools:W5")]


def test_a_symbol_that_is_not_w_n_sorts_last_instead_of_raising() -> None:
    # luthen's committed history holds `R-amtool`, which is not a W<n>.
    new = {"waypoints": [_wp("W10"), _wp("R-amtool"), _wp("W2")], "residue": []}
    d = diff({}, new)
    assert d.minted == ["W2", "W10", "R-amtool"]


def test_a_repo_with_no_queue_yet_reads_as_empty() -> None:
    d = diff({}, {"waypoints": [_wp("W1", "done")], "residue": []})
    assert d.minted == ["W1"] and d.closed == ["W1"]


def _commit(repo: Path, queue: dict, when: str) -> str:
    path = repo / ".claude" / "paths-forward.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(queue))
    env = {
        "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_DATE": when,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin",
    }
    for args in (["add", "-A"], ["commit", "-q", "-m", "q"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=env)
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _two_commits(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "a"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    first = _commit(
        repo, {"waypoints": [_wp("W1")], "residue": []}, "2026-10-01T12:00:00Z"
    )
    _commit(
        repo,
        {"waypoints": [_wp("W1", "done"), _wp("W2")], "residue": []},
        "2026-10-05T12:00:00Z",
    )
    return repo, first


def test_the_history_is_read_by_revision_and_by_date(tmp_path: Path) -> None:
    repo, first = _two_commits(tmp_path)
    assert queue_at(repo, first)["waypoints"][0]["status"] == "ready"
    assert resolve(repo, "2026-09-30") is None  # before the first commit
    assert resolve(repo, "2026-10-03") == first  # the last commit before the date
    assert queue_at(repo, resolve(repo, "2026-09-30")) == {}


def test_a_baseline_time_with_no_zone_is_refused(tmp_path: Path) -> None:
    """nemik:W1127: 14:20 with no zone was read as local time and printed a plausible answer."""
    repo, _ = _two_commits(tmp_path)
    refused = ""
    try:
        resolve(repo, "2026-10-26T14:20")
    except ValueError as error:
        refused = str(error)
    assert "no zone" in refused


def test_a_baseline_time_with_a_zone_or_a_window_names_an_exact_instant(
    tmp_path: Path,
) -> None:
    """Z and an offset name one instant; -1h and -99999d count back from now."""
    repo, first = _two_commits(tmp_path)
    assert resolve(repo, "2026-10-01T11:59:00Z") is None
    assert resolve(repo, "2026-10-01T12:01:00Z") == first
    assert resolve(repo, "2026-10-01T08:01:00-04:00") == first
    assert resolve(repo, "-99999d") is None
    assert resolve(repo, "ago:99999d") is None
    assert resolve(repo, "ago:1h") == resolve(repo, "-1h")
    # the second commit, days old, is the last one before an hour ago
    assert resolve(repo, "-1h") != first


def test_time_in_state_and_the_weekly_roll_up_follow_the_commits(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "a"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    _commit(
        repo,
        {"waypoints": [_wp("W1", "blocked"), _wp("W2")], "residue": []},
        "2026-10-05T12:00:00Z",  # Monday of ISO week 41
    )
    _commit(
        repo,
        {"waypoints": [_wp("W1", "blocked"), _wp("W2", "done")], "residue": []},
        "2026-10-07T12:00:00Z",
    )
    _commit(
        repo,
        {"waypoints": [_wp("W1", "ready"), _wp("W2", "done")], "residue": []},
        "2026-10-13T12:00:00Z",  # week 42
    )
    snaps = snapshots(repo)
    spent = time_in_state(snaps, datetime(2026, 10, 14, 12, tzinfo=UTC))
    day = 86400
    assert spent["W1"] == {"blocked": 8 * day, "ready": 1 * day}
    assert spent["W2"] == {"ready": 2 * day, "done": 7 * day}
    w41, w42 = weekly(snaps)
    assert (w41["week"], w41["opened"], w41["closed"]) == ("2026-W41", 2, 1)
    assert w41["blocked_share"] == 1.0  # W1 is the only open card and it is blocked
    assert (w41["oldest_blocked"], w41["oldest_blocked_days"]) == ("W1", 2.0)
    assert (w42["opened"], w42["closed"], w42["blocked_share"]) == (0, 0, 0.0)
    assert w42["oldest_blocked"] is None
    # nemik:W315: W2 was first committed Oct 5 and closed Oct 7: a lead time of 2 days, that week
    # only.
    assert w41["lead_time_days"] == 2.0 and w42["lead_time_days"] is None
    # nemik:W325: two arrived, one left: utilization 2.0; W1 is the one open card, so at one close a
    # week a new card waits 1 / 1 * 7 days. nemik:W328: W2 was never marked working: efficiency 0.
    assert (w41["utilization"], w41["implied_wait_days"]) == (2.0, 7.0)
    assert w41["flow_efficiency"] == 0.0
    assert w42["utilization"] is None and w42["flow_efficiency"] is None


def test_the_static_history_names_no_waypoint_and_passes_the_manifest(
    tmp_path: Path,
) -> None:
    # nemik:W308: history.json is counts and days; the oldest-blocked symbol is dropped.
    from nemik.manifest import unmanifested
    from nemik.serve import history_doc

    _two_commits(tmp_path)
    doc = history_doc(tmp_path)
    assert list(doc) == ["a"]
    assert all("oldest_blocked" not in row for row in doc["a"])
    assert {"week", "opened", "closed", "open", "blocked_share"} <= set(doc["a"][0])
    assert unmanifested("history.json", doc) == []


def test_a_withheld_waypoint_is_not_counted_in_the_published_history(
    tmp_path: Path,
) -> None:
    # nemik:W309: _two_commits mints W1 then W2; withholding a:W2 leaves one opened card.
    from nemik.serve import history_doc

    _two_commits(tmp_path)
    full = sum(row["opened"] for row in history_doc(tmp_path)["a"])
    kept = sum(row["opened"] for row in history_doc(tmp_path, frozenset({"a:W2"}))["a"])
    assert (full, kept) == (2, 1)


def test_the_command_prints_the_diff_between_two_dates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_commits(tmp_path)
    code = main(["a", "--from", "2026-10-02", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "a: 1 minted, 1 closed, 0 dropped" in out
    assert "minted: W2" in out and "closed: W1" in out


def test_each_forecast_issue_is_appended_after_the_last(tmp_path: Path) -> None:
    """Two issues into one shingle file leave both, the second after the first."""
    _two_commits(tmp_path)
    shingle = tmp_path / "shingle.tsv"
    argv = ["a", "--forecast", "--root", str(tmp_path), "--append-to", str(shingle)]
    assert main(argv) == 0
    first = shingle.read_text(encoding="utf-8")
    assert main(argv) == 0
    both = shingle.read_text(encoding="utf-8")
    assert both.startswith(first)
    assert len(both.splitlines()) == 2 * len(first.splitlines())
