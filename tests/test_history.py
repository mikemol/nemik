"""nemik:W267: nemik-history diffs a repo's committed queue between two revisions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from nemik.history import diff, main, queue_at, resolve


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


def test_the_command_prints_the_diff_between_two_dates(tmp_path: Path, capsys) -> None:
    _two_commits(tmp_path)
    code = main(["a", "--from", "2026-10-02", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "a: 1 minted, 1 closed, 0 dropped" in out
    assert "minted: W2" in out and "closed: W1" in out
