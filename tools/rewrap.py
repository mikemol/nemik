# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1225: re-wrap the comment and docstring lines that pass the line limit.

It rewrites layout only: a too-long comment line or docstring body line is split at the last space
before the limit, and the words and their order are untouched. It leaves alone a docstring's first
line (splitting a summary would make ruff's D205 fire), a line with no space to split at, a
directive comment (noqa, type, fmt, pragma), and a doctest line.

    python tools/rewrap.py FILE... [--write] [--width N]

Without --write it prints how many lines it would change in each file and writes nothing.
"""

import argparse
import ast
import sys
from pathlib import Path

WIDTH = 100
DIRECTIVES = ("noqa", "type:", "fmt:", "pragma", "pylint", "ruff:", "isort:", "!")


def _docstring_lines(tree: ast.AST) -> tuple[set[int], set[int]]:
    """Find the docstring lines of a module.

    Returns:
        The body lines of every docstring, and the first line of each (which is never split).

    """
    body: set[int] = set()
    first: set[int] = set()
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, kinds) or not node.body:
            continue
        head = node.body[0]
        if not isinstance(head, ast.Expr):
            continue
        value = head.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        first.add(head.lineno)
        body.update(range(head.lineno, (head.end_lineno or head.lineno) + 1))
    return body, first


def _split(line: str, text: str, head: str, width: int) -> list[str]:
    # split `text` into lines that each start with `head` and fit `width`; `line` when it cannot
    out: list[str] = []
    current = ""
    for word in text.split(" "):
        trial = word if not current else current + " " + word
        if current and len(head + trial) > width:
            out.append(head + current)
            current = word
        else:
            current = trial
    out.append(head + current)
    return out if len(out) > 1 else [line]


def _comment_text(stripped: str) -> str:
    # the words of a comment line after its hash, or "" when it is a directive or one word
    text = stripped[1:].strip()
    if " " not in text or text.startswith(DIRECTIVES):
        return ""
    return text


def rewrap(source: str, width: int = WIDTH) -> str:
    """Re-wrap the too-long comment and docstring body lines of a module.

    Args:
        source: The module text.
        width: The line limit.

    Returns:
        The module text with those lines split; the same text when none is too long.

    """
    body, first = _docstring_lines(ast.parse(source))
    out: list[str] = []
    for number, line in enumerate(source.split("\n"), start=1):
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if len(line) <= width:
            out.append(line)
        elif stripped.startswith("#"):
            text = _comment_text(stripped)
            out.extend(_split(line, text, indent + "# ", width) if text else [line])
        elif number in body and number not in first and not stripped.startswith(">>>"):
            out.extend(_split(line, stripped, indent, width))
        else:
            out.append(line)
    return "\n".join(out)


class _Options(argparse.Namespace):
    """The command line, typed."""

    files: list[Path]
    write: bool
    width: int


def main(argv: list[str] | None = None) -> int:
    """Re-wrap the named files, or report how many lines each would change.

    Returns:
        0.

    """
    parser = argparse.ArgumentParser(
        description="re-wrap long comment and docstring lines"
    )
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--width", type=int, default=WIDTH)
    args = parser.parse_args(argv, namespace=_Options())
    changed = 0
    for path in args.files:
        before = path.read_text(encoding="utf-8")
        after = rewrap(before, args.width)
        if after == before:
            continue
        changed += 1
        added = len(after.split("\n")) - len(before.split("\n"))
        sys.stdout.write(f"{path}: +{added} lines\n")
        if args.write:
            path.write_text(after, encoding="utf-8")
    verb = "rewritten" if args.write else "would change"
    sys.stdout.write(f"{changed} of {len(args.files)} files {verb}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
