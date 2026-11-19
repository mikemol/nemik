# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2343: the commit hook's git-fed checks, as pure functions over a facts text.

The hook judged three things in shell, from git. Every file under src/nemik and tests is named
in bazel/nemik_src.bzl and bazel/nemik_tests.bzl (nemik:W2087, the operator's ruling that inputs
are named from `git ls-files`). Every wheel the pyproject.toml names is tracked (nemik:W276). And
code or tests changed while the queue has ready cards and no working one (nemik:W319).

A bazel test is hermetic and cannot run git, so git's answers arrive as DATA: the gate writes
them into a facts file from the STAGED tree, and each check here is judged by its own cached
bazel test that declares that file as an input (the operator, host transcript 695f3e0a line
190734: work with bazel's cache, never around it).

A facts text is `tree <40 hex>` on its first line, the staged tree's sha, then one path per
line. The stamp is how a stale file is caught: `require_tree` refuses facts that describe
another tree than the one the caller says it is judging, so facts cannot silently lie. Every
check returns its problems as a list, empty when there are none; a malformed or stale facts
text is an exception, never an empty list.
"""

import re
from typing import NamedTuple

from nemik_src import SRC_SPEC, TESTS_SPEC, check

STAMP = "tree"
STAMP_FIELDS = 2
SHA = re.compile(r"[0-9a-f]{40}")
WHEEL = re.compile(r'vendor/wheels/[^"]*\.whl')
CODE_TREES = ("src/", "tests/")
READY = '"status": "ready"'
WORKING = '"status": "working"'
NO_WORKING_CARD = (
    "code or tests changed, the queue has ready cards, and none is marked working"
)


class FactsError(ValueError):
    """A facts text is malformed or stale; the message names its source."""


class Facts(NamedTuple):
    """What a facts file says: the tree it describes and the paths git reported for it."""

    tree: str
    paths: list[str]


def parse(text: str, source: str) -> Facts:
    """Read a facts text.

    Args:
        text: The facts file's text.
        source: Where it came from, for the error message.

    Returns:
        The stamp and the paths.

    Raises:
        FactsError: the first line is not `tree <40 hex>`.

    """
    lines = text.splitlines()
    head = lines[0].split(" ") if lines else []
    if len(head) != STAMP_FIELDS or head[0] != STAMP or not SHA.fullmatch(head[1]):
        msg = f"{source}: the first line is not '{STAMP} <40 hex>'"
        raise FactsError(msg)
    return Facts(head[1], [line for line in lines[1:] if line])


def require_tree(facts: Facts, expected: str, source: str) -> None:
    """Refuse facts that do not describe the tree being judged.

    Args:
        facts: The parsed facts.
        expected: The staged tree's sha, as the caller learned it apart from the facts file.
        source: Where the facts came from, for the error message.

    Raises:
        FactsError: `expected` is not a sha (the caller did not say which tree), or the facts
            were written for another tree.

    """
    if not SHA.fullmatch(expected):
        msg = f"{source}: the tree to judge against is not a 40 hex sha ({expected!r})"
        raise FactsError(msg)
    if facts.tree != expected:
        msg = (
            f"{source}: the facts describe tree {facts.tree} and the staged tree is "
            f"{expected}: the facts are stale"
        )
        raise FactsError(msg)


def _under(facts: Facts, tree: str) -> list[str]:
    return [path for path in facts.paths if path.startswith(f"{tree}/")]


def named_inputs_problems(tracked: Facts, src_list: str, tests_list: str) -> list[str]:
    """Compare both named-inputs lists with the tracked paths.

    Args:
        tracked: The tracked paths of the staged tree.
        src_list: The text of bazel/nemik_src.bzl.
        tests_list: The text of bazel/nemik_tests.bzl.

    Returns:
        One problem per list that is not exactly what `tools/nemik_src.py --write` renders.

    """
    return [
        *check(src_list, _under(tracked, SRC_SPEC.tree), SRC_SPEC),
        *check(tests_list, _under(tracked, TESTS_SPEC.tree), TESTS_SPEC),
    ]


def wheel_problems(tracked: Facts, pyproject: str) -> list[str]:
    """Name each wheel the pyproject.toml lists that the staged tree does not track.

    Args:
        tracked: The tracked paths of the staged tree.
        pyproject: The text of pyproject.toml.

    Returns:
        One problem per wheel named and not tracked (a rebuilt wheel is hidden by .gitignore).

    """
    have = set(tracked.paths)
    named = sorted({str(match.group(0)) for match in WHEEL.finditer(pyproject)})
    return [
        f"not tracked (git add -f): {wheel}" for wheel in named if wheel not in have
    ]


def working_card_problems(queue: str, changed: Facts) -> list[str]:
    """Apply the working-card rule.

    A commit that changes code or tests while the queue has ready cards and NO working card is
    refused; a queue-only commit and a queue with nothing ready are exempt. The queue text is
    matched as the hook matched it, on the writer's canonical `"status": "ready"` spelling.

    Args:
        queue: The staged .claude/paths-forward.json text.
        changed: The paths the commit changes against HEAD.

    Returns:
        The refusal, or nothing.

    """
    code = [path for path in changed.paths if path.startswith(CODE_TREES)]
    if code and READY in queue and WORKING not in queue:
        return [NO_WORKING_CARD]
    return []
