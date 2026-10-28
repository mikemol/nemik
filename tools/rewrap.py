# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1225: re-wrap the comment and docstring lines that pass the line limit.

It rewrites layout only: a too-long comment line or docstring body line is split at the last space
before the limit, the words that no longer fit move to the start of the next line of the same
paragraph (and so on down it), and the words and their order are untouched. It leaves alone a
docstring's first line (splitting a summary would make ruff's D205 fire), a line with no space to
split at, a directive comment (noqa, type, fmt, pragma), and a doctest line.

    python tools/rewrap.py FILE... [--write] [--width N]

Without --write it prints how many lines it would change in each file and writes nothing.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

WIDTH = 100
DIRECTIVES = ("noqa", "type:", "fmt:", "pragma", "pylint", "ruff:", "isort:", "!")
ITEM = re.compile(r"([-*+]|\d+[.)]) ")


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


def _words(head: str, text: str, width: int) -> list[str]:
    # greedy fill of `text` into lines that each fit `width` after `head`; one word may overflow
    out: list[str] = []
    current = ""
    for word in text.split(" "):
        trial = word if not current else current + " " + word
        if current and len(head + trial) > width:
            out.append(current)
            current = word
        else:
            current = trial
    out.append(current)
    return out


def _comment_text(stripped: str) -> str:
    # the words of a comment line after its hash, or "" when it is a directive or one word
    text = stripped[1:].strip()
    if " " not in text or text.startswith(DIRECTIVES):
        return ""
    return text


def _read(
    number: int, line: str, body: set[int], first: set[int]
) -> tuple[bool, str, str]:
    # whether this tool may reflow the line, and its head (indent and comment marker) and text
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    if stripped.startswith("#"):
        text = _comment_text(stripped)
        return (True, indent + "# ", text) if text else (False, "", "")
    skip = stripped.startswith((">>>", '"""', '"'))
    if number in body and number not in first and stripped and not skip:
        return True, indent, stripped
    return False, "", ""


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
    carry = ""
    carry_head = ""
    for number, line in enumerate(source.split("\n"), start=1):
        reflow, head, text = _read(number, line, body, first)
        merged = False
        if carry:
            if reflow and head == carry_head and not ITEM.match(text):
                text = carry + " " + text
                merged = True
            else:
                out.append(carry_head + carry)
            carry = ""
        if not reflow:
            out.append(line)
        elif len(head + text) > width and " " in text:
            parts = _words(head, text, width)
            out.extend(head + part for part in parts[:-1])
            carry, carry_head = parts[-1], head
        else:
            out.append(head + text if merged else line)
    if carry:
        out.append(carry_head + carry)
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
        sys.stdout.write(f"{path}: {added:+d} lines\n")
        if args.write:
            path.write_text(after, encoding="utf-8")
    verb = "rewritten" if args.write else "would change"
    sys.stdout.write(f"{changed} of {len(args.files)} files {verb}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
