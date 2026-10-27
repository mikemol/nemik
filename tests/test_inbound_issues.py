# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1169: a repo's letters are read from an issue list by the labels of inbox-as-issues."""

import json

import pytest

from nemik.inbound_issues import census, letters_of, unclaimed


def _issue(
    number: int, labels: list[str], state: str = "open", *, pull: bool = False
) -> dict[str, object]:
    issue: dict[str, object] = {
        "number": number,
        "title": f"letter {number}",
        "state": state,
        "body": "please do x",
        "html_url": f"https://example.test/o/r/issues/{number}",
        "labels": [{"name": name} for name in labels],
        "locked": False,
    }
    if pull:
        issue["pull_request"] = {"url": "x"}
    return issue


ROWS: list[dict[str, object]] = [
    _issue(1, ["from:linux-sources", "kind:ask", "cites:nemik:W1049"]),
    _issue(2, ["from:linux-sources", "kind:info"], "closed"),
    _issue(3, ["from:mtools", "kind:ask"]),
    _issue(4, ["bug"]),
    _issue(5, ["from:mtools", "kind:ask"], pull=True),
]
ISSUES = json.dumps(ROWS)


def test_a_kind_label_makes_a_letter_and_a_pull_request_or_plain_issue_is_not() -> None:
    """Five issues, three letters: the plain issue and the pull request are left out."""
    letters = letters_of(ISSUES)
    assert [letter["title"] for letter in letters] == [
        "letter 1",
        "letter 2",
        "letter 3",
    ]
    assert letters[0] == {
        "url": "https://example.test/o/r/issues/1",
        "title": "letter 1",
        "state": "open",
        "from": "linux-sources",
        "kind": "ask",
        "cites": "nemik:W1049",
    }
    assert not letters[2]["cites"]


def test_an_open_letter_no_waypoint_cites_is_unclaimed() -> None:
    """A letter is claimed by its cites label or its URL appearing in the queue."""
    letters = letters_of(ISSUES)
    by_cite = unclaimed(letters, '{"evidence": "see nemik:W1049"}')
    assert [letter["title"] for letter in by_cite] == ["letter 3"]
    by_url = unclaimed(letters, "https://example.test/o/r/issues/3 nemik:W1049")
    assert by_url == []
    assert [letter["title"] for letter in unclaimed(letters, "")] == [
        "letter 1",
        "letter 3",
    ]


def test_the_census_counts_by_sender_and_kind_sorted() -> None:
    """Lines to compare by value: sender, kind, open and closed."""
    assert census(letters_of(ISSUES)) == [
        "linux-sources ask open=1 closed=0",
        "linux-sources info open=0 closed=1",
        "mtools ask open=1 closed=0",
    ]


def test_a_list_of_the_wrong_shape_or_not_json_is_refused() -> None:
    """The tracker reader's errors pass through."""
    with pytest.raises(TypeError):
        letters_of("{}")
    with pytest.raises(ValueError, match=r"."):
        letters_of("not json")
