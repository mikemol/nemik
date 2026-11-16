# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1083: a candidate's newest commit subject is shown beside what its card says is left."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mikemol.procrun.proc import capture

from nemik.history import main
from nemik.workmarks import head, idle, leading, pair

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

SUBJECTS = [
    "W7: second slice of the thing",
    "W9: unrelated",
    "not a card commit",
    "W7: first slice of the thing",
    "Wx: not a number",
    "W12 no colon",
]


def test_head_reads_only_a_symbol_before_the_first_colon() -> None:
    """A subject leads a card only when W<digits> precedes its first colon."""
    assert head("W7: a thing") == "W7"
    assert not head("Wx: a thing")
    assert not head("W12 no colon")
    assert not head("see W7: later")


def test_leading_keeps_the_newest_subject_of_each_card() -> None:
    """Subjects come newest first, so the first met for a symbol is the one kept."""
    assert leading(SUBJECTS) == {
        "W7": "W7: second slice of the thing",
        "W9": "W9: unrelated",
    }


def test_pair_shows_the_done_when_beside_the_subject() -> None:
    """A ready card that leads a commit gets both its subject and its stated next step."""
    lines = pair({"W7": "Build the second half", "W3": "never landed"}, SUBJECTS)
    assert lines == [
        "W7\n  landed: W7: second slice of the thing\n  left:   Build the second half"
    ]


def test_pair_says_when_a_card_states_no_next_step() -> None:
    """A blank next step is stated, not silently dropped (a mutant would print an empty left)."""
    lines = pair({"W9": "  "}, SUBJECTS)
    assert lines == [
        "W9\n  landed: W9: unrelated\n  left:   (the card states no next step)"
    ]


def test_pair_closes_nothing_and_lists_in_symbol_order() -> None:
    """Candidates come sorted by symbol, and a card with no commit has no line at all."""
    lines = pair({"W9": "b", "W7": "a"}, SUBJECTS)
    assert [line.split("\n")[0] for line in lines] == ["W7", "W9"]
    assert pair({"W5": "x"}, SUBJECTS) == []


def test_idle_lists_a_working_card_not_worked_since_the_cutoff() -> None:
    """A stamp before the cutoff is idle, one at or after it is not, and none at all is idle."""
    working = {
        "W3": "2026-11-16T08:00:00Z",
        "W1": "2026-11-16T09:30:00Z",
        "W2": "2026-11-16T09:00:00Z",
        "W4": "",
    }
    assert idle(working, "2026-11-16T09:30:00Z") == ["W2", "W3", "W4"]
    assert idle({}, "2026-11-16T09:30:00Z") == []


def _git(repo: Path, *args: str) -> None:
    """Run git in `repo` as a fixed author and fail the test when it exits nonzero."""
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin",
    }
    done = capture(["git", "-C", str(repo), *args], env=env)
    assert done.returncode == 0, done.stderr


def _card(symbol: str, status: str, step: str, worked: str = "") -> dict[str, str]:
    """Build one queue card with the fields the mode reads.

    Returns:
        The card as the queue file stores it.

    """
    return {
        "symbol": symbol,
        "status": status,
        "next_bounded_step": step,
        "last_worked": worked,
    }


def test_the_mode_prints_a_ready_candidate_beside_its_next_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On a real repo a ready card leading a commit is listed; a blocked one is not."""
    repo = tmp_path / "demo"
    (repo / ".claude").mkdir(parents=True)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    cards = [
        _card("W1", "ready", "finish the second half"),
        _card("W2", "blocked", "wait"),
        _card("W3", "ready", "never committed"),
        _card("W4", "working", "", "2020-01-01T00:00:00Z"),
        _card("W5", "working", "", now),
    ]
    doc = {"waypoints": cards}
    (repo / ".claude" / "paths-forward.json").write_text(
        json.dumps(doc), encoding="utf-8"
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "W1: first half")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "W2: a blocked card's commit")
    assert main(["demo", "--landed-open", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "demo: 1 ready card(s) lead a landed commit" in out
    assert "left:   finish the second half" in out
    assert "W2" not in out
    assert "W3" not in out
    assert "demo: 1 working card(s) idle since before" in out
    assert "W4\n  last worked: 2020-01-01T00:00:00Z" in out
    assert "W5" not in out
