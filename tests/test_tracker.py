# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W957: a tracker's issue is read, typed, from what GitHub and Forgejo really send."""

from pathlib import Path

import pytest

from nemik.tracker import (
    BOOL,
    DICT,
    INT,
    LIST,
    MISSING,
    NULL,
    REAL,
    STR,
    Tree,
    parse_tree,
    read_issue,
)

HERE = Path(__file__).parent
TRACKERS = HERE / "fixtures" / "trackers"
GITHUB_NUMBER = 2000
LAST = 2  # the value of the second "a" in the repeated-member test
NESTED = (
    '{"a": "x\\n\\u00e9\\ud83d\\ude00", "b": [1, -2, 3.5, 1e2], '
    '"c": {"d": [null, true]}}'
)


def _fixture(name: str) -> str:
    """Read a recorded issue.

    Returns:
        Its text.

    """
    return (TRACKERS / name).read_text(encoding="utf-8")


def _plain(tree: Tree, at: int) -> object:
    """Turn a parsed value into the plain Python value it stands for.

    Returns:
        A dict, list, str, bool, int, float or None.

    """
    kind = tree.kinds[at]
    plain: object = None
    if kind == DICT:
        plain = {
            name: _plain(tree, kid)
            for name, kid in zip(tree.names[at], tree.kids[at], strict=True)
        }
    elif kind == LIST:
        plain = [_plain(tree, kid) for kid in tree.kids[at]]
    elif kind == STR:
        plain = tree.texts[at]
    elif kind == BOOL:
        plain = tree.flags[at]
    elif kind == INT:
        plain = tree.wholes[at]
    elif kind == REAL:
        plain = tree.reals[at]
    return plain


def test_the_recorded_github_issue_is_read() -> None:
    """An open issue with three labels, not a pull request, not locked."""
    issue = read_issue(_fixture("github_issue.json"))
    assert issue.number == GITHUB_NUMBER
    assert issue.title == "Support different default OWNER in `gh repo clone REPO`"
    assert issue.state == "open"
    assert issue.labels == ["enhancement", "gh-repo", "help wanted candidate"]
    assert issue.url == "https://github.com/cli/cli/issues/2000"
    assert not issue.is_pull_request
    assert not issue.locked
    assert "default OWNER" in issue.body


def test_the_recorded_forgejo_issue_is_read() -> None:
    """A closed issue with no labels and a null pull_request: not a pull request."""
    issue = read_issue(_fixture("forgejo_issue.json"))
    assert issue.number == 1
    assert issue.title == "Configure Woodpecker"
    assert issue.state == "closed"
    assert issue.labels == []
    assert not issue.is_pull_request
    assert issue.body.startswith("https://ci.codeberg.org/")
    assert "[x] set the timeout to 2h" in issue.body


def test_an_object_under_pull_request_marks_a_pull_request() -> None:
    """GitHub's issues endpoint returns pull requests too, marked by a pull_request object."""
    issue = read_issue('{"number": 7, "title": "t", "pull_request": {"url": "u"}}')
    assert issue.is_pull_request
    assert read_issue('{"number": 7, "is_locked": true}').locked


def test_the_parser_reads_escapes_numbers_and_nesting() -> None:
    """Escapes, a surrogate pair, ints and floats, nulls and nested containers."""
    tree = parse_tree(NESTED)
    assert _plain(tree, tree.root) == {
        "a": "x\né\U0001f600",
        "b": [1, -2, 3.5, 100.0],
        "c": {"d": [None, True]},
    }


def test_a_missing_member_reads_as_null_and_a_repeated_one_takes_the_last() -> None:
    """The lookup never fails: a member that is absent is the null, and the last of two wins."""
    tree = parse_tree('{"a": 1, "a": 2, "b": null}')
    assert tree.wholes[tree.get(tree.root, "a")] == LAST
    assert tree.kinds[tree.get(tree.root, "b")] == NULL
    assert tree.get(tree.root, "zzz") == MISSING
    assert not tree.string(tree.root, "a")


@pytest.mark.parametrize(
    "text",
    ['{"a":', "tru", '{"a": 1} x', '"open', '"\\q"', '"\\ud83d"', "[1,", ""],
)
def test_text_that_is_not_json_raises_value_error(text: str) -> None:
    """A truncated, misspelt, trailing or badly escaped text is refused, never half-read."""
    with pytest.raises(ValueError, match="offset"):
        parse_tree(text)


@pytest.mark.parametrize(
    "text",
    [
        "[1]",
        '{"title": "no number"}',
        '{"number": true}',
        '{"number": 1, "labels": {}}',
    ],
)
def test_json_of_the_wrong_shape_raises_type_error(text: str) -> None:
    """Valid JSON that is not an issue is a different error from text that is not JSON."""
    with pytest.raises(TypeError):
        read_issue(text)
