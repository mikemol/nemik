# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2343: the hook's git-fed checks as pure functions, tested on fixtures with no git."""

import pytest
from hook_facts import (
    NO_WORKING_CARD,
    Diff,
    Facts,
    FactsError,
    named_inputs_problems,
    parse,
    parse_diff,
    require_diff,
    require_tree,
    wheel_problems,
    working_card_problems,
)
from nemik_src import SRC_SPEC, TESTS_SPEC, render

TREE = "a" * 40
OTHER = "b" * 40
HEAD = "c" * 40
MODULES = ["src/nemik/__init__.py", "src/nemik/a.py", "src/nemik/b.py"]
TESTS = ["tests/test_a.py", "tests/conftest.py"]
SRC_LIST = render(MODULES, SRC_SPEC)
TESTS_LIST = render(TESTS, TESTS_SPEC)
READY = '{"waypoints": [{"symbol": "W1", "status": "ready"}]}'
WORKING = '{"waypoints": [{"symbol": "W1", "status": "ready"}, {"status": "working"}]}'
DONE = '{"waypoints": [{"symbol": "W1", "status": "done"}]}'
TRACKED_HEAD = f"facts tracked\ntree {TREE}\nhead {HEAD}\n"
CHANGED_HEAD = f"facts changed\ntree {TREE}\nhead {HEAD}\n"


def _facts(*paths: str, tree: str = TREE, head: str = HEAD) -> Facts:
    return Facts(tree, head, list(paths))


def _diff(*paths: str, tree: str = TREE, head: str = HEAD) -> Diff:
    return Diff(tree, head, list(paths))


def test_a_facts_text_is_a_kind_two_stamps_then_one_path_per_line() -> None:
    """The first line names the kind, then the tree and HEAD; blank lines are not paths."""
    text = f"{TRACKED_HEAD}src/nemik/a.py\n\ntests/test_a.py\n"
    paths = ["src/nemik/a.py", "tests/test_a.py"]
    assert parse(text, "t.txt") == Facts(TREE, HEAD, paths)
    assert parse(TRACKED_HEAD, "t.txt") == Facts(TREE, HEAD, [])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "src/nemik/a.py\n",
        f"tree {TREE}\n",
        f"facts changed\ntree {TREE}\nhead {HEAD}\n",
        f"Facts tracked\ntree {TREE}\n",
        f"facts tracked x\ntree {TREE}\n",
    ],
)
def test_a_text_that_is_not_a_tracked_file_is_refused_with_its_source_named(
    text: str,
) -> None:
    """The first line must name the tracked kind, so another file's text is not read as paths."""
    with pytest.raises(FactsError, match="first line is not 'facts tracked'") as raised:
        parse(text, "gate/tracked.txt")
    assert str(raised.value).startswith("gate/tracked.txt:")


@pytest.mark.parametrize(
    "text",
    [
        "facts tracked\n",
        "facts tracked\ntree\n",
        f"facts tracked\ntree {TREE} x\n",
        "facts tracked\ntree xyz\n",
        f"facts tracked\nTree {TREE}\n",
    ],
)
def test_a_tracked_text_without_a_good_stamp_is_refused_naming_the_line(
    text: str,
) -> None:
    """No stamp means nothing says which tree the paths describe."""
    with pytest.raises(
        FactsError, match="second line is not 'tree <40 hex>'"
    ) as raised:
        parse(text, "gate/tracked.txt")
    assert str(raised.value).startswith("gate/tracked.txt:")


@pytest.mark.parametrize(
    "stamps",
    [
        "",
        "src/nemik/a.py\n",
        f"head {HEAD}\n",
        f"tree {TREE}\n",
        f"tree {TREE}\nhead\n",
        f"tree {TREE}\nhead xyz\n",
        f"tree {TREE}\ntree {HEAD}\n",
        f"tree {TREE}\nHead {HEAD}\n",
    ],
)
def test_a_tracked_text_without_a_head_stamp_is_refused_naming_the_line(
    stamps: str,
) -> None:
    """Every judgment is stamped with the HEAD too (nemik:W2345): a path is never read as one."""
    with pytest.raises(FactsError, match="line is not '") as raised:
        parse(f"facts tracked\n{stamps}", "gate/tracked.txt")
    assert str(raised.value).startswith("gate/tracked.txt:")


def test_a_diff_text_is_a_kind_two_stamps_then_one_path_per_line() -> None:
    """The changed paths name the tree AND the HEAD they were diffed against."""
    text = f"{CHANGED_HEAD}README.md\n\nsrc/nemik/b.py\n"
    assert parse_diff(text, "c.txt") == Diff(
        TREE, HEAD, ["README.md", "src/nemik/b.py"]
    )
    assert parse_diff(CHANGED_HEAD, "c.txt") == Diff(TREE, HEAD, [])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "README.md\n",
        f"tree {TREE}\nhead {HEAD}\n",
        f"facts tracked\ntree {TREE}\n",
        f"Facts changed\ntree {TREE}\nhead {HEAD}\n",
    ],
)
def test_a_text_that_is_not_a_changed_file_is_refused_with_its_source_named(
    text: str,
) -> None:
    """The first line must name the changed kind, so another file's text is not read as paths."""
    with pytest.raises(FactsError, match="first line is not 'facts changed'") as raised:
        parse_diff(text, "gate/changed.txt")
    assert str(raised.value).startswith("gate/changed.txt:")


@pytest.mark.parametrize(
    ("stamps", "where"),
    [
        ("", "second"),
        (f"tree {TREE}\n", "third"),
        (f"tree {TREE}\nREADME.md\n", "third"),
        (f"tree {TREE}\ntree {HEAD}\n", "third"),
        (f"tree {TREE}\nhead xyz\n", "third"),
        (f"head {HEAD}\ntree {TREE}\n", "second"),
    ],
)
def test_a_diff_text_without_both_stamps_is_refused_naming_the_line(
    stamps: str, where: str
) -> None:
    """A changed-paths file with only a tree stamp is the gap the cold review found."""
    with pytest.raises(FactsError, match=f"the {where} line is not '") as raised:
        parse_diff(f"facts changed\n{stamps}", "gate/changed.txt")
    assert str(raised.value).startswith("gate/changed.txt:")


def test_each_parser_refuses_the_other_files_text() -> None:
    """The planted red of nemik:W2350: a changed text read as tracked once passed require_tree."""
    changed = f"{CHANGED_HEAD}README.md\n"
    tracked = f"{TRACKED_HEAD}src/nemik/a.py\n"
    with pytest.raises(FactsError, match=r"\('facts changed'\)"):
        parse(changed, "gate/tracked.txt")
    with pytest.raises(FactsError, match=r"\('facts tracked'\)"):
        parse_diff(tracked, "gate/changed.txt")


def test_facts_for_another_tree_are_refused_as_stale() -> None:
    """The mismatch the card asks for: facts cannot silently describe an older tree."""
    require_tree(_facts("src/nemik/a.py"), TREE, "tracked.txt")
    with pytest.raises(FactsError, match="stale"):
        require_tree(_facts("src/nemik/a.py", tree=OTHER), TREE, "tracked.txt")


@pytest.mark.parametrize("expected", ["", "unset", "a" * 39, "A" * 40])
def test_a_caller_that_does_not_say_the_tree_is_refused_not_trusted(
    expected: str,
) -> None:
    """An unset or malformed expected tree is an error, never a pass."""
    with pytest.raises(FactsError, match="not a 40 hex sha"):
        require_tree(_facts("src/nemik/a.py"), expected, "tracked.txt")


def test_changed_paths_for_another_head_or_tree_are_refused_as_stale() -> None:
    """One tree against two HEADs is two different bodies, so the stamp must name both."""
    require_diff(_diff("README.md"), TREE, HEAD, "changed.txt")
    with pytest.raises(FactsError, match="stale"):
        require_diff(_diff("README.md", head=OTHER), TREE, HEAD, "changed.txt")
    with pytest.raises(FactsError, match="stale"):
        require_diff(_diff("README.md", tree=OTHER), TREE, HEAD, "changed.txt")


@pytest.mark.parametrize(
    ("tree", "head"), [("", HEAD), (TREE, ""), ("unset", "unset"), (TREE, "c" * 39)]
)
def test_a_caller_that_does_not_say_the_tree_and_head_is_refused(
    tree: str, head: str
) -> None:
    """An unsayable tree or HEAD is an error, never a pass."""
    with pytest.raises(FactsError, match="not a 40 hex sha"):
        require_diff(_diff("README.md"), tree, head, "changed.txt")


def test_a_current_pair_of_lists_has_no_named_inputs_problem() -> None:
    """The lists are exactly what the tool renders for the tracked paths."""
    tracked = _facts(*MODULES, *TESTS, "tests/data.json", "README.md")
    assert named_inputs_problems(tracked, SRC_LIST, TESTS_LIST) == []


def test_a_tracked_module_no_list_names_is_the_w1997_refusal() -> None:
    """A new src/nemik module with no entry in bazel/nemik_src.bzl."""
    tracked = _facts(*MODULES, "src/nemik/rolling.py", *TESTS)
    problems = named_inputs_problems(tracked, SRC_LIST, TESTS_LIST)
    assert len(problems) == 1
    assert "bazel/nemik_src.bzl" in problems[0]
    assert "src/nemik/rolling.py" in problems[0]


def test_a_test_file_the_tests_list_lacks_and_a_named_one_gone_are_both_found() -> None:
    """Missing and extra, in the tests list."""
    tracked = _facts(*MODULES, "tests/test_a.py", "tests/test_new.py")
    problems = named_inputs_problems(tracked, SRC_LIST, TESTS_LIST)
    assert len(problems) == 1
    assert "bazel/nemik_tests.bzl" in problems[0]
    assert "tests/test_new.py" in problems[0]
    assert "tests/conftest.py" in problems[0]


def test_a_wheel_the_pyproject_names_must_be_tracked() -> None:
    """vendor/wheels/.gitignore hides a rebuilt wheel, so it can exist and not be committed."""
    pyproject = 'deps = ["x @ file:vendor/wheels/x-1.0-py3-none-any.whl"]\n'
    assert (
        wheel_problems(_facts("vendor/wheels/x-1.0-py3-none-any.whl"), pyproject) == []
    )
    problems = wheel_problems(_facts("src/nemik/a.py"), pyproject)
    assert problems == [
        "not tracked (git add -f): vendor/wheels/x-1.0-py3-none-any.whl"
    ]
    assert wheel_problems(_facts(), "deps = []\n") == []


@pytest.mark.parametrize(
    ("queue", "changed", "expected"),
    [
        (READY, ["src/nemik/a.py"], [NO_WORKING_CARD]),
        (READY, ["tests/test_a.py"], [NO_WORKING_CARD]),
        (WORKING, ["src/nemik/a.py"], []),
        (DONE, ["src/nemik/a.py"], []),
        (READY, [".claude/paths-forward.json"], []),
        (READY, [], []),
    ],
)
def test_the_working_card_rule_is_the_hooks_rule(
    queue: str, changed: list[str], expected: list[str]
) -> None:
    """Code or tests changed, ready cards and no working one: refused; anything else passes."""
    assert working_card_problems(queue, _diff(*changed)) == expected
