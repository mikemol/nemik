# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2343: the hook's git-fed checks as pure functions, tested on fixtures with no git."""

import pytest
from hook_facts import (
    NO_WORKING_CARD,
    Facts,
    FactsError,
    named_inputs_problems,
    parse,
    require_tree,
    wheel_problems,
    working_card_problems,
)
from nemik_src import SRC_SPEC, TESTS_SPEC, render

TREE = "a" * 40
OTHER = "b" * 40
MODULES = ["src/nemik/__init__.py", "src/nemik/a.py", "src/nemik/b.py"]
TESTS = ["tests/test_a.py", "tests/conftest.py"]
SRC_LIST = render(MODULES, SRC_SPEC)
TESTS_LIST = render(TESTS, TESTS_SPEC)
READY = '{"waypoints": [{"symbol": "W1", "status": "ready"}]}'
WORKING = '{"waypoints": [{"symbol": "W1", "status": "ready"}, {"status": "working"}]}'
DONE = '{"waypoints": [{"symbol": "W1", "status": "done"}]}'


def _facts(*paths: str, tree: str = TREE) -> Facts:
    return Facts(tree, list(paths))


def test_a_facts_text_is_a_stamp_then_one_path_per_line() -> None:
    """The first line names the tree; blank lines are not paths."""
    text = f"tree {TREE}\nsrc/nemik/a.py\n\ntests/test_a.py\n"
    assert parse(text, "t.txt") == Facts(TREE, ["src/nemik/a.py", "tests/test_a.py"])
    assert parse(f"tree {TREE}\n", "t.txt") == Facts(TREE, [])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "src/nemik/a.py\n",
        "tree\n",
        f"tree {TREE} x\n",
        "tree xyz\n",
        f"Tree {TREE}\n",
    ],
)
def test_a_text_without_a_good_stamp_is_refused_with_its_source_named(
    text: str,
) -> None:
    """No stamp means nothing says which tree the paths describe."""
    with pytest.raises(FactsError, match="first line is not 'tree <40 hex>'") as raised:
        parse(text, "gate/tracked.txt")
    assert str(raised.value).startswith("gate/tracked.txt:")


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
    assert working_card_problems(queue, _facts(*changed)) == expected
