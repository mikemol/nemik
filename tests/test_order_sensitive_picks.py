# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W541: no test or tool takes the first of an unsorted directory listing.

Five image builds failed on a pick like `next(root.glob("*"))`: Bazel and the host happened to list
files in an order that passed, and the Forgejo build's filesystem did not. This reads every Python
file under tests/, tools/ and checks/ and refuses `next(...)` or `[0]` / `[-1]` over a glob, rglob,
iterdir, listdir or scandir call that is not wrapped in `sorted(...)`.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREES = ("tests", "tools", "checks")
LISTING = frozenset({"glob", "rglob", "iterdir", "listdir", "scandir"})
PICKED = (0, -1)


def _is_listing(node: ast.AST) -> bool:
    """Say whether a node is a call to a directory-listing function.

    Args:
        node: Any AST node.

    Returns:
        True for `x.glob(...)`, `listdir(...)` and the like.

    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in LISTING
    return isinstance(func, ast.Name) and func.id in LISTING


def _unsorted_listing(node: ast.AST) -> bool:
    """Say whether a subtree holds a listing call that is not inside `sorted(...)`.

    Args:
        node: The root of the subtree.

    Returns:
        True when some listing call there has no `sorted` above it within the subtree.

    """
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sorted"
    ):
        return False
    if _is_listing(node):
        return True
    return any(_unsorted_listing(child) for child in ast.iter_child_nodes(node))


def _picks_over_listing(source: str) -> list[int]:
    """Find the lines that pick one item from an unsorted listing.

    Args:
        source: Python source text.

    Returns:
        The line numbers of `next(...)` and `[0]` / `[-1]` over an unsorted listing.

    """
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "next"
            and node.args
            and _unsorted_listing(node.args[0])
        ):
            lines.append(node.lineno)
        if (
            isinstance(node, ast.Subscript)
            and _literal_index(node.slice) in PICKED
            and _unsorted_listing(node.value)
        ):
            lines.append(node.lineno)
    return sorted(lines)


def _literal_index(node: ast.AST) -> int | None:
    """Read a subscript as an integer literal, negative ones included.

    Args:
        node: The subscript's slice.

    Returns:
        The integer, or None when it is not a literal integer.

    """
    try:
        value: object = ast.literal_eval(node)
    except ValueError:
        return None
    return value if isinstance(value, int) else None


def test_no_file_picks_the_first_of_an_unsorted_listing() -> None:
    """Every Python file under tests/, tools/ and checks/ sorts a listing before picking."""
    found = [
        f"{path.relative_to(ROOT)}:{line}"
        for tree in TREES
        if (ROOT / tree).is_dir()
        for path in sorted((ROOT / tree).glob("*.py"))
        for line in _picks_over_listing(path.read_text(encoding="utf-8"))
    ]
    assert found == [], "\n".join(found)


def test_the_unsorted_forms_are_caught() -> None:
    """The shapes that failed the image build are all named."""
    assert _picks_over_listing("x = next(p.glob('*'))\n") == [1]
    assert _picks_over_listing("x = next(iter(p.iterdir()))\n") == [1]
    assert _picks_over_listing("x = list(p.glob('*'))[0]\n") == [1]
    assert _picks_over_listing("x = os.listdir(d)[-1]\n") == [1]
    assert _picks_over_listing("x = next(f for f in p.rglob('*.py'))\n") == [1]


def test_the_sorted_forms_pass() -> None:
    """Sorting first, or picking from a non-listing, is fine."""
    assert _picks_over_listing("x = sorted(p.glob('*'))[0]\n") == []
    assert _picks_over_listing("x = next(iter(sorted(p.iterdir())))\n") == []
    assert _picks_over_listing("x = items[0]\n") == []
    assert _picks_over_listing("x = len(list(p.glob('*')))\n") == []
