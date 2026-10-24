# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W370: a poll of a tracker's issues asks the queue to mint, suggest, or nothing."""

from pathlib import Path

from nemik.events import WRITER
from nemik.pollevents import poll_lines
from nemik.tracker import Issue, read_issue

TRACKERS = Path(__file__).parent / "fixtures" / "trackers"
REPO = "me/tracker"


def _issue(
    number: int, state: str, body: str, *, pull_request: bool = False, title: str = ""
) -> Issue:
    """Make an issue with a state and a body.

    Returns:
        The issue.

    """
    return Issue(
        number=number,
        title=title or f"title {number}",
        state=state,
        body=body,
        labels=[],
        url=f"u{number}",
        is_pull_request=pull_request,
        locked=False,
    )


def test_an_open_issue_nemik_did_not_mirror_is_a_card_to_mint() -> None:
    """The recorded GitHub issue is open and foreign: the lines are the command to add a card."""
    issue = read_issue((TRACKERS / "github_issue.json").read_text(encoding="utf-8"))
    assert poll_lines([issue], REPO) == [
        "# me/tracker#2000 open: https://github.com/cli/cli/issues/2000",
        f"{WRITER} --add 'Support different default OWNER in `gh repo clone REPO`'",
    ]


def test_a_closed_foreign_issue_asks_nothing() -> None:
    """The recorded Forgejo issue is closed and not nemik's: nothing to do."""
    issue = read_issue((TRACKERS / "forgejo_issue.json").read_text(encoding="utf-8"))
    assert poll_lines([issue], REPO) == []


def test_a_closed_mirrored_issue_suggests_the_card_is_done() -> None:
    """The card named in the body gets a suggested status change, not a write."""
    got = poll_lines([_issue(5, "closed", "nemik card alpha:W12")], REPO)
    assert got == [
        "# me/tracker#5 closed: u5",
        f"# suggest, if alpha:W12 is this repo's card: {WRITER} --update W12 --status done",
    ]


def test_an_open_mirrored_issue_and_a_pull_request_ask_nothing() -> None:
    """An issue nemik wrote that is still open, and a pull request, are both left alone."""
    quiet = [
        _issue(1, "open", "nemik card alpha:W1"),
        _issue(2, "open", "an idea", pull_request=True),
        _issue(3, "closed", "nemik card alpha:W3", pull_request=True),
    ]
    assert poll_lines(quiet, REPO) == []


def test_a_title_with_a_semicolon_or_a_quote_is_made_safe() -> None:
    """The writer refuses semicolons in titles, and a quote must survive the shell."""
    odd = _issue(9, "open", "", title="it's; done")
    assert poll_lines([odd], REPO)[1] == f"{WRITER} --add 'it'\\''s, done'"
