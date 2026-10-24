# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W958: the calls a mirror would make against a tracker's recorded issues."""

from pathlib import Path

from nemik.issues import plan_text
from nemik.mirror import changes
from nemik.projection import Task

TRACKERS = Path(__file__).parent / "fixtures" / "trackers"
MIRRORED = (
    '[{"number": 1, "title": "old title", "state": "open", "html_url": "u1",'
    ' "body": "nemik card alpha:W1", "labels": [{"name": "alpha"}]},'
    ' {"number": 2, "title": "second", "state": "open", "html_url": "u2",'
    ' "body": "nemik card alpha:W2", "labels": [{"name": "alpha"}]},'
    ' {"number": 3, "title": "somebody else", "state": "open", "html_url": "u3",'
    ' "body": "unrelated", "labels": []},'
    ' {"number": 4, "title": "a change", "state": "open", "html_url": "u4",'
    ' "body": "nemik card alpha:W9", "labels": [], "pull_request": {"url": "p"}}]'
)
TASKS = [
    Task(uid=1, cite="alpha:W1", name="new title", done=False),
    Task(uid=2, cite="alpha:W2", name="second", done=True),
    Task(uid=3, cite="alpha:W3", name="third", done=False),
]


def test_update_close_create_and_leave_alone() -> None:
    """A retitled card updates its title, a finished one closes, a new one is created whole."""
    lines = plan_text(TASKS, MIRRORED).splitlines()
    assert lines == [
        "update alpha:W1 title",
        "close alpha:W2",
        "create alpha:W3 blocked_by,body,cite,labels,state,title",
        "skipped pull request #4",
        "3 call(s) against 3 issue(s) of the tracker",
    ]


def test_a_pull_request_naming_a_card_is_not_a_mirror_of_it() -> None:
    """The pull request that says `nemik card alpha:W9` is skipped, so W9 would be created."""
    nine = [Task(uid=9, cite="alpha:W9", name="nine", done=False)]
    first = plan_text(nine, MIRRORED).splitlines()[0]
    assert first.startswith("create alpha:W9 ")


def test_the_recorded_real_issues_are_left_alone() -> None:
    """A real GitHub and a real Forgejo issue were not mirrored by nemik: nothing is changed."""
    github = (TRACKERS / "github_issue.json").read_text(encoding="utf-8")
    forgejo = (TRACKERS / "forgejo_issue.json").read_text(encoding="utf-8")
    one = [Task(uid=1, cite="alpha:W1", name="a card", done=False)]
    lines = plan_text(one, f"[{github}, {forgejo}]").splitlines()
    assert lines[0].startswith("create alpha:W1 ")
    assert lines[-1] == "1 call(s) against 2 issue(s) of the tracker"


def test_a_field_the_tracker_does_not_carry_is_unknown_not_different() -> None:
    """blocked_by is absent from an issue payload, so it is not rewritten."""
    want: dict[str, object] = {
        "title": "t",
        "body": "b",
        "labels": ["a"],
        "blocked_by": ["x:W1"],
    }
    have: dict[str, object] = {"title": "t", "body": "b", "labels": ["a"]}
    assert changes(want, have) == {}
    have["blocked_by"] = []
    assert changes(want, have) == {"blocked_by": ["x:W1"]}
