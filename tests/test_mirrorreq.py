# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W959: a mirror plan's calls become the GitHub or Forgejo requests, with no network."""

import pytest

from nemik.mirror import Call
from nemik.mirrorreq import FORGEJO, GITHUB, Request, numbers, requests_for
from nemik.tracker import Issue

FIELDS: dict[str, object] = {
    "title": "t",
    "body": "nemik card a:W3",
    "labels": ["a"],
    "state": "open",
    "blocked_by": ["a:W1"],
}


def _issue(number: int, body: str, *, pull_request: bool = False) -> Issue:
    """Make an open issue with a body, a pull request when asked.

    Returns:
        The issue.

    """
    issue = Issue(number)
    issue.title = f"t{number}"
    issue.state = "open"
    issue.body = body
    issue.url = f"u{number}"
    issue.is_pull_request = pull_request
    return issue


ISSUES = [
    _issue(7, "nemik card a:W1"),
    _issue(8, "nemik card a:W2"),
    _issue(9, "nemik card a:W4", pull_request=True),
    _issue(10, "unrelated"),
]
CALLS: list[Call] = [
    ("create", "a:W3", FIELDS),
    ("update", "a:W1", {"title": "new", "labels": ["a", "b"]}),
    ("close", "a:W2", {}),
    ("reopen", "a:W1", {}),
]


def test_issue_numbers_come_from_the_mirrored_issues_only() -> None:
    """A pull request naming a card and an issue naming none are not the card's issue."""
    assert numbers(ISSUES) == {"a:W1": 7, "a:W2": 8}


def test_github_requests() -> None:
    """Create posts title, body and label names; changes patch the issue number."""
    got = requests_for(GITHUB, "me/repo", CALLS, numbers(ISSUES))
    assert got == [
        Request(
            "POST",
            "/repos/me/repo/issues",
            {"title": "t", "body": "nemik card a:W3", "labels": ["a"]},
        ),
        Request(
            "PATCH", "/repos/me/repo/issues/7", {"title": "new", "labels": ["a", "b"]}
        ),
        Request("PATCH", "/repos/me/repo/issues/8", {"state": "closed"}),
        Request("PATCH", "/repos/me/repo/issues/7", {"state": "open"}),
    ]


def test_forgejo_requests_are_under_api_v1_and_carry_no_label_names() -> None:
    """Forgejo's create takes label ids, which nemik does not know, so labels are left out."""
    got = requests_for(FORGEJO, "me/repo", CALLS, numbers(ISSUES))
    assert got[0] == Request(
        "POST",
        "/api/v1/repos/me/repo/issues",
        {"title": "t", "body": "nemik card a:W3"},
    )
    assert got[1] == Request(
        "PATCH", "/api/v1/repos/me/repo/issues/7", {"title": "new"}
    )
    assert len(got) == len(CALLS)


def test_a_labels_only_update_on_forgejo_sends_nothing() -> None:
    """A call that changes only a field the tool does not take gives no request."""
    only: list[Call] = [("update", "a:W1", {"labels": ["b"]})]
    assert requests_for(FORGEJO, "me/repo", only, {"a:W1": 7}) == []


def test_blocked_by_is_never_in_a_body() -> None:
    """The dependency edges are separate endpoints, so no create body carries them."""
    for tool in (GITHUB, FORGEJO):
        first = requests_for(tool, "me/repo", CALLS[:1], {})[0]
        assert "blocked_by" not in first.body
        assert "state" not in first.body


def test_an_unknown_tool_or_an_issue_the_tracker_lacks_is_refused() -> None:
    """Neither guesses: a card with no issue cannot be updated, a tool must be one of two."""
    with pytest.raises(ValueError, match="unknown tool"):
        requests_for("jira", "me/repo", CALLS[:1], {})
    with pytest.raises(ValueError, match="no issue number for a:W1"):
        requests_for(GITHUB, "me/repo", CALLS[1:2], {})
