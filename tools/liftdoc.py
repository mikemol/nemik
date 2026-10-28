# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1225: lift a comment that opens an undocumented function into its docstring.

A public module-level function with no docstring whose first statement has a prose comment right
above it (the author's own account of what it does) gets that comment as its docstring: the first
sentence is the summary, the rest follows a blank line, and the comment lines are removed (moved,
not copied). A comment is left alone when it carries a directive, has no sentence ending in a
period, has a first sentence too long for one line (a wrapped summary would swap ruff's D103 for
D205), starts with a lowercase plain word (D403), is a diagram, or opens a function that is not a
test with a plain word (ruff's D401 wants an imperative verb there, and skips only test names).

    python tools/liftdoc.py FILE... [--write] [--sample N] [--width N]

Without --write it prints what it would lift and why it skips the rest, and writes nothing.
"""

import argparse
import ast
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

WIDTH = 100
DIRECTIVES = ("noqa", "type:", "fmt:", "pragma", "pylint", "ruff:", "isort:", "!")


@dataclass(frozen=True)
class Lift:
    """One function's comment, and what became of it."""

    name: str
    first: int
    last: int
    docstring: list[str]
    skipped: str


def _fill(indent: str, text: str, width: int) -> list[str]:
    # greedy fill of `text` into lines that each fit `width` after `indent`
    out: list[str] = []
    current = ""
    for word in text.split(" "):
        trial = word if not current else current + " " + word
        if current and len(indent + trial) > width:
            out.append(indent + current)
            current = word
        else:
            current = trial
    out.append(indent + current)
    return out


def _why_not(text: str, name: str) -> str:
    # the reason a comment's text cannot be a docstring whatever its length, or ""
    if text.startswith(DIRECTIVES):
        return "directive"
    plain = text.partition(" ")[0].replace("'", "").isalpha()
    if plain and text[:1].islower():
        return "starts with a lowercase plain word"
    if plain and not name.startswith("test"):
        return "not a test, so the first word must be an imperative verb"
    return ""


def _sentence(text: str) -> tuple[str, str]:
    # the first sentence of the text and the rest, or ("", "") when none ends in a period
    cut = text.find(". ")
    if cut >= 0:
        return text[: cut + 1], text[cut + 2 :]
    if text.endswith("."):
        return text, ""
    return "", ""


def _docstring(indent: str, text: str, width: int, name: str) -> tuple[list[str], str]:
    # the docstring lines for a comment's text, or the reason it cannot be lifted
    why = _why_not(text, name)
    if why:
        return [], why
    first, rest = _sentence(text)
    if not first:
        return [], "no sentence ending in a period"
    if " <- " in first or "{" in first:
        return [], "a diagram, not prose"
    if len(first) > width - len(indent) - 3 - (0 if rest else 3):
        return [], "first sentence over one line"
    if not rest:
        return [f'{indent}"""{first}"""'], ""
    return [f'{indent}"""{first}', "", *_fill(indent, rest, width), f'{indent}"""'], ""


def lifts(source: str, width: int = WIDTH) -> list[Lift]:
    """Find the comments that open undocumented public functions and decide each.

    Args:
        source: The module text.
        width: The line limit.

    Returns:
        One Lift per such function: its docstring lines when it can be lifted, else the reason not.

    """
    lines = source.split("\n")
    out: list[Lift] = []
    for node in ast.parse(source).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_") or ast.get_docstring(node) is not None:
            continue
        stmt = node.body[0].lineno - 1
        if stmt == node.lineno - 1:
            continue
        top = stmt
        while top > 0 and lines[top - 1].lstrip().startswith("#"):
            top -= 1
        if top == stmt:
            continue
        indent = lines[stmt][: len(lines[stmt]) - len(lines[stmt].lstrip())]
        text = " ".join(row.lstrip()[1:].strip() for row in lines[top:stmt])
        docstring, why = _docstring(indent, text, width, node.name)
        out.append(Lift(node.name, top, stmt, docstring, why))
    return out


def _bottom_up(one: Lift) -> int:
    # sort key: the lift lowest in the file first, so earlier line numbers stay valid
    return -one.first


def lift(source: str, width: int = WIDTH) -> str:
    """Move each liftable comment into its function's docstring.

    Args:
        source: The module text.
        width: The line limit.

    Returns:
        The module text with those comments replaced by docstrings.

    """
    lines = source.split("\n")
    liftable = [x for x in lifts(source, width) if not x.skipped]
    for one in sorted(liftable, key=_bottom_up):
        lines[one.first : one.last] = one.docstring
    return "\n".join(lines)


class _Options(argparse.Namespace):
    """The command line, typed."""

    files: list[Path]
    write: bool
    sample: int
    width: int


def main(argv: list[str] | None = None) -> int:
    """Report, or perform, the lifts in the named files.

    Returns:
        0.

    """
    parser = argparse.ArgumentParser(
        description="lift opening comments into docstrings"
    )
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--width", type=int, default=WIDTH)
    args = parser.parse_args(argv, namespace=_Options())
    done: list[tuple[str, Lift]] = []
    reasons: Counter[str] = Counter()
    for path in args.files:
        before = path.read_text(encoding="utf-8")
        found = lifts(before, args.width)
        for one in found:
            if one.skipped:
                reasons[one.skipped] += 1
            else:
                done.append((path.name, one))
        if args.write and any(not x.skipped for x in found):
            path.write_text(lift(before, args.width), encoding="utf-8")
    sys.stdout.write(f"{len(done)} lifted, {sum(reasons.values())} skipped\n")
    for reason, count in reasons.most_common():
        sys.stdout.write(f"  skipped {count}: {reason}\n")
    step = max(1, len(done) // args.sample) if args.sample else 1
    for name, one in done[::step][: args.sample]:
        sys.stdout.write(f"--- {name}::{one.name}\n" + "\n".join(one.docstring) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
