# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W706: browser tests wait on the page's own event, never on a wall-clock bound.

Playwright's `wait_for_function` fails after `timeout` milliseconds (30 s by default, 60 s in
many of nemik's tests). On a loaded host that bound fails a test the gate passed on the same
tree (the image build of 406e3bd). `timeout=0` disables the bound, so the wait ends when the
page raises the event and the harness's own resource bound ends a page that never does.

This rewrites every `<x>.wait_for_function(...)` call in the files it is given so its timeout
is 0: a `timeout=N` keyword has its value replaced, a call without one gains `timeout=0`.
Nothing else is touched. It prints a unified diff and writes nothing unless `--write` is
given, and a second run changes nothing. Written to be lifted by other repos' browser tests.
Run `ruff format` on the files it wrote.

    python tools/webpage_waits.py tests/test_*.py            dry run: the diff
    python tools/webpage_waits.py --write tests/test_*.py    apply
"""

import ast
import difflib
import sys
from pathlib import Path

CALL = "wait_for_function"
NO_BOUND = b"0"
Span = tuple[int, int, bytes]


def line_starts(data: bytes) -> list[int]:
    """Give the byte offset at which each source line starts.

    Args:
        data: The source as bytes.

    Returns:
        One offset per line, in order.

    """
    starts = [0]
    for index, byte in enumerate(data):
        if byte == ord("\n"):
            starts.append(index + 1)
    return starts


def replace_bound(node: ast.keyword, data: bytes, starts: list[int]) -> list[Span]:
    """Give the span that sets an existing timeout keyword's value to 0.

    Args:
        node: The `timeout=...` keyword.
        data: The source as bytes.
        starts: The line start offsets.

    Returns:
        One span, or none when the value is already 0.

    """
    value = node.value
    begin = starts[value.lineno - 1] + value.col_offset
    stop = starts[(value.end_lineno or 1) - 1] + (value.end_col_offset or 0)
    if data[begin:stop] == NO_BOUND:
        return []
    return [(begin, stop, NO_BOUND)]


def add_bound(call: ast.Call, data: bytes, starts: list[int]) -> Span:
    """Give the span that adds timeout=0 before a call's closing parenthesis.

    Args:
        call: The call without a timeout keyword.
        data: The source as bytes.
        starts: The line start offsets.

    Returns:
        The insertion, placed after the last argument and its comma if it has one.

    """
    close = starts[(call.end_lineno or 1) - 1] + (call.end_col_offset or 0) - 1
    last = close
    while data[last - 1 : last].isspace():
        last -= 1
    text = b" timeout=0," if data[last - 1 : last] == b"," else b", timeout=0"
    return (last, last, text)


def edits(data: bytes) -> list[Span]:
    """Find the byte spans to change so each wait_for_function call has timeout=0.

    Args:
        data: The source as bytes.

    Returns:
        (start, end, replacement) spans, in source order.

    """
    starts = line_starts(data)
    found: list[Span] = []
    for node in ast.walk(ast.parse(data)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != CALL:
            continue
        bound = next((kw for kw in node.keywords if kw.arg == "timeout"), None)
        if bound is None:
            found.append(add_bound(node, data, starts))
        else:
            found.extend(replace_bound(bound, data, starts))
    return sorted(found)


def rewrite(source: str) -> str:
    """Rewrite one file's source so no wait_for_function call has a wall-clock bound.

    Args:
        source: The file's text.

    Returns:
        The text with every such call's timeout set to 0; unchanged when there are none.

    """
    data = source.encode("utf-8")
    for begin, stop, text in reversed(edits(data)):
        data = data[:begin] + text + data[stop:]
    return data.decode("utf-8")


def offset(starts: list[int], line: int, col: int) -> int:
    """Turn a node's (line, column) into a byte offset.

    Args:
        starts: The line start offsets.
        line: The 1-based line.
        col: The byte column.

    Returns:
        The byte offset into the source.

    """
    return starts[line - 1] + col


def span_of(node: ast.expr, starts: list[int]) -> tuple[int, int]:
    """Give the byte span a node covers.

    Args:
        node: An expression node.
        starts: The line start offsets.

    Returns:
        (start, end) offsets into the source.

    """
    begin = offset(starts, node.lineno, node.col_offset)
    stop = offset(starts, node.end_lineno or 1, node.end_col_offset or 0)
    return begin, stop


def until_edit(
    node: ast.Call, data: bytes, starts: list[int]
) -> tuple[Span, str] | None:
    """Give the span that rewrites `X.wait_for_function(E, timeout=0)` as `webpage.until(X, E)`.

    Args:
        node: A call node.
        data: The source as bytes.
        starts: The line start offsets.

    Returns:
        The span and the page's name, or None when the call is some other shape (more arguments,
        another keyword).

    """
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != CALL:
        return None
    if not isinstance(func.value, ast.Name) or len(node.args) != 1:
        return None
    if [kw.arg for kw in node.keywords] != ["timeout"]:
        return None
    begin, stop = span_of(node, starts)
    first, last = span_of(node.args[0], starts)
    name = func.value.id
    text = b"webpage.until(" + name.encode() + b", " + data[first:last] + b")"
    return (begin, stop, text), name


def watch_edits(tree: ast.AST, starts: list[int], waited: set[str]) -> list[Span]:
    """Give the spans that put `webpage.watch(X)` above each `X.goto(...)` statement.

    Args:
        tree: The parsed file.
        starts: The line start offsets.
        waited: The page names whose waits were rewritten.

    Returns:
        One insertion per such statement.

    """
    found: list[Span] = []
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not (isinstance(func, ast.Attribute) and func.attr == "goto"):
            continue
        if isinstance(func.value, ast.Name) and func.value.id in waited:
            at = offset(starts, stmt.lineno, stmt.col_offset)
            watch = b"webpage.watch(" + func.value.id.encode() + b")\n"
            found.append((at, at, watch + b" " * stmt.col_offset))
    return found


def adopt_edits(data: bytes) -> list[Span]:
    """Find the spans that move a file's waits onto webpage.until and watch its pages.

    Only a file that imports webpage is touched. Each `X.wait_for_function(E, timeout=0)` becomes
    `webpage.until(X, E)`, and each `X.goto(...)` statement for such an X gains a
    `webpage.watch(X)` line above it, so the page's errors are recorded from its first load.

    Args:
        data: The source as bytes.

    Returns:
        (start, end, replacement) spans, in source order.

    """
    tree = ast.parse(data)
    imported = any(
        isinstance(n, ast.Import) and any(a.name == "webpage" for a in n.names)
        for n in ast.walk(tree)
    )
    if not imported:
        return []
    starts = line_starts(data)
    found: list[Span] = []
    waited: set[str] = set()
    for node in ast.walk(tree):
        edit = until_edit(node, data, starts) if isinstance(node, ast.Call) else None
        if edit is not None:
            found.append(edit[0])
            waited.add(edit[1])
    return sorted([*found, *watch_edits(tree, starts, waited)])


def adopt(source: str) -> str:
    """Move a file's waits onto webpage.until and watch its pages.

    Args:
        source: The file's text.

    Returns:
        The rewritten text; unchanged when the file does not import webpage or has no such call.

    """
    data = source.encode("utf-8")
    for begin, stop, text in reversed(adopt_edits(data)):
        data = data[:begin] + text + data[stop:]
    return data.decode("utf-8")


def run(names: list[str], *, write: bool, adopting: bool = False) -> int:
    """Print the diff for each file, or write the rewrite.

    Args:
        names: The files to rewrite.
        write: Whether to write the files instead of printing the diff.
        adopting: Whether to move the waits onto webpage.until instead of unbounding them.

    Returns:
        How many files change.

    """
    changed = 0
    for name in names:
        path = Path(name)
        before = path.read_text(encoding="utf-8")
        after = adopt(before) if adopting else rewrite(before)
        if after == before:
            continue
        changed += 1
        if write:
            path.write_text(after, encoding="utf-8")
            continue
        old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
        sys.stdout.writelines(difflib.unified_diff(old, new, name, name))
    return changed


def main(argv: list[str]) -> int:
    """Run over the files named in argv, writing only with --write.

    Args:
        argv: The command-line arguments after the program name.

    Returns:
        0.

    """
    write = "--write" in argv
    adopting = "--adopt" in argv
    names = [arg for arg in argv if not arg.startswith("--")]
    changed = run(names, write=write, adopting=adopting)
    verb = "rewritten" if write else "would change"
    sys.stdout.write(f"{changed} file(s) {verb}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
