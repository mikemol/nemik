# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W980: which rule, and which file, holds most of a ratchet baseline.

A ratchet baseline here is {file: {rule: count}} (ruff-baseline.json, mypy-baseline.json). The
operator's ruling (host 695f3e0a line 92679) makes every nonzero baseline a pay-down priority, and
paying one down starts with knowing where the weight is. This totals the counts by rule and by
file and prints the heaviest, so the pay-down card picks its target by measurement.

    python3 -m nemik.baselinetop ruff-baseline.json [how-many]
"""

import sys
from pathlib import Path

from nemik.tracker import DICT, INT, parse_tree

SHOWN = 12


def _counts(text: str) -> list[tuple[str, str, int]]:
    """Read a baseline into (file, rule, count) rows.

    Returns:
        One row per file and rule.

    Raises:
        TypeError: When the baseline is not an object of objects of integers.

    """
    tree = parse_tree(text)
    top = tree.root
    if tree.kinds[top] != DICT:
        message = "a baseline is an object of files"
        raise TypeError(message)
    rows: list[tuple[str, str, int]] = []
    for at, name in enumerate(tree.names[top]):
        rules = tree.kids[top][at]
        if tree.kinds[rules] != DICT:
            message = f"{name} is not an object of rules"
            raise TypeError(message)
        for place, rule in enumerate(tree.names[rules]):
            count = tree.kids[rules][place]
            if tree.kinds[count] != INT:
                message = f"{name} {rule} is not a count"
                raise TypeError(message)
            rows.append((name, rule, tree.wholes[count]))
    return rows


def _heaviest(totals: dict[str, int]) -> list[tuple[str, int]]:
    """Order totals heaviest first, ties by name.

    Returns:
        The (key, total) pairs.

    """
    return sorted(totals.items(), key=_by_weight)


def _by_weight(item: tuple[str, int]) -> tuple[int, str]:
    """Sort key: the larger total first, then the name.

    Returns:
        The key.

    """
    return -item[1], item[0]


def by_rule(text: str) -> list[tuple[str, int]]:
    """Total a baseline's counts by rule.

    Args:
        text: The baseline's JSON.

    Returns:
        (rule, total) pairs, heaviest first.

    """
    totals: dict[str, int] = {}
    for _, rule, count in _counts(text):
        totals[rule] = totals.get(rule, 0) + count
    return _heaviest(totals)


def by_file(text: str) -> list[tuple[str, int]]:
    """Total a baseline's counts by file.

    Args:
        text: The baseline's JSON.

    Returns:
        (file, total) pairs, heaviest first.

    """
    totals: dict[str, int] = {}
    for name, _, count in _counts(text):
        totals[name] = totals.get(name, 0) + count
    return _heaviest(totals)


def main(argv: list[str]) -> int:
    """Print the heaviest rules and files of a baseline file.

    Returns:
        0 on success, 2 when no file is named.

    """
    if not argv:
        sys.stderr.write("usage: baselinetop BASELINE.json [HOW-MANY]\n")
        return 2
    text = Path(argv[0]).read_text(encoding="utf-8")
    shown = int(argv[1]) if len(argv) > 1 else SHOWN
    sys.stdout.write("by rule:\n")
    for rule, total in by_rule(text)[:shown]:
        sys.stdout.write(f"{total:6} {rule}\n")
    sys.stdout.write("by file:\n")
    for name, total in by_file(text)[:shown]:
        sys.stdout.write(f"{total:6} {name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
