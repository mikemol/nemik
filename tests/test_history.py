"""nemik:W267: nemik-history diffs a repo's committed queue between two revisions."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from nemik.history import (
    diff,
    main,
    queue_at,
    resolve,
    snapshots,
    time_in_state,
    weekly,
)


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


def test_the_command_prints_the_diff_between_two_dates(tmp_path: Path, capsys) -> None:
    _two_commits(tmp_path)
    code = main(["a", "--from", "2026-10-02", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "a: 1 minted, 1 closed, 0 dropped" in out
    assert "minted: W2" in out and "closed: W1" in out
