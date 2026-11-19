# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2018: each repo's surfaces census side by side, aligned by surface.

`mikemol-surfaces [REPO_DIR]` (mtools' hooks wheel) prints ONE repo's census as a schema-1 JSON
document: {"schema": 1, "repo": <dirname>, "surfaces": [{"surface", "declared", "changed_by",
"loaded_by", "reviewed_by"}, ...]}. Each repo reads only itself; the fleet view is made here, over
documents already collected, so nothing in this file reads a repository. How a repo's document
reaches us is mtools:W2754 (each repo publishes `.claude/surfaces.export.json`); this tool takes
the files as arguments.

A surface a repo does not list is ABSENT, and Absent is a type of its own (a cell is either a
census entry or `ABSENT`), never None and never a made-up value, so a reader cannot mistake it
for a declared False. The table prints it as `-`. A row is marked `*` when its cells are not all
present and equal, so the differences are what the eye finds.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple

SCHEMA = 1
FIELDS = ("declared", "changed_by", "loaded_by", "reviewed_by")
BAD_INPUT = 2


class Absent:
    """The cell of a repo that does not list the surface: a type, not a value."""

    __slots__ = ()


ABSENT = Absent()

type Cell = dict[str, object] | Absent


class CensusError(ValueError):
    """A document is not a usable schema-1 surfaces census; the message names its source."""


class Census(NamedTuple):
    """One repo's census: its name, the surfaces in the order it listed them, and their fields."""

    repo: str
    order: list[str]
    fields: dict[str, dict[str, object]]


class Row(NamedTuple):
    """One surface across repos: a cell per repo, ABSENT where the repo lists no such surface."""

    surface: str
    cells: list[Cell]


class Options(argparse.Namespace):
    """The parsed command line."""

    files: list[Path]


def _dict(value: object) -> dict[str, object]:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _loads(text: str) -> object:
    value: object = json.loads(text)
    return value


def parse(doc: object, source: str) -> Census:
    """Read one schema-1 document.

    Args:
        doc: The parsed JSON.
        source: Where it came from, for the error message.

    Returns:
        The census.

    Raises:
        CensusError: the document is not schema 1, names no repo, or has a surface that is
            unnamed, repeated or lacks one of the four fields.

    """
    body = _dict(doc)
    if body.get("schema") != SCHEMA:
        msg = f"{source}: not a schema-{SCHEMA} surfaces census"
        raise CensusError(msg)
    repo = body.get("repo")
    if (
        not isinstance(repo, str)
        or not repo
        or not isinstance(body.get("surfaces"), list)
    ):
        msg = f"{source}: no repo name, or no surfaces list"
        raise CensusError(msg)
    order: list[str] = []
    fields: dict[str, dict[str, object]] = {}
    for entry in _list(body.get("surfaces")):
        item = _dict(entry)
        name = item.get("surface")
        if not isinstance(name, str) or not name:
            msg = f"{source}: a surface entry has no name"
            raise CensusError(msg)
        if name in fields:
            msg = f"{source}: surface {name} is listed twice"
            raise CensusError(msg)
        lacking = [f for f in FIELDS if f not in item]
        if lacking:
            msg = f"{source}: surface {name} lacks {', '.join(lacking)}"
            raise CensusError(msg)
        order.append(name)
        fields[name] = {f: item[f] for f in FIELDS}
    return Census(repo, order, fields)


def load(path: Path) -> Census:
    """Read one census file.

    Returns:
        The census.

    Raises:
        CensusError: the file cannot be read, is not JSON, or is not a census; the message
            names the file.

    """
    try:
        doc = _loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"{path}: {exc}"
        raise CensusError(msg) from exc
    return parse(doc, str(path))


def align(censuses: list[Census]) -> tuple[list[str], list[Row]]:
    """Line the censuses up by surface.

    Returns:
        The repo names in sorted order, and one row per surface in order of first appearance
        (the repos are walked in that sorted order; mtools prints a fixed order, so for real
        documents it is the same order throughout).

    Raises:
        CensusError: two documents name the same repo.

    """
    repos = sorted(c.repo for c in censuses)
    if len(set(repos)) != len(repos):
        msg = "two documents name the same repo"
        raise CensusError(msg)
    by_repo = {c.repo: c for c in censuses}
    surfaces: list[str] = []
    for repo in repos:
        surfaces += [s for s in by_repo[repo].order if s not in surfaces]
    return repos, [
        Row(s, [by_repo[r].fields.get(s, ABSENT) for r in repos]) for s in surfaces
    ]


def differs(row: Row) -> bool:
    """Say whether a row's cells are not all present and equal.

    Returns:
        True when any repo lacks the surface or two repos carry different fields.

    """
    first = row.cells[0]
    return isinstance(first, Absent) or any(c != first for c in row.cells)


def _cell(cell: Cell) -> str:
    if isinstance(cell, Absent):
        return "-"
    values: list[object] = [cell[f] for f in FIELDS]
    return json.dumps(values, separators=(",", ":"))


def render(repos: list[str], rows: list[Row]) -> str:
    """Print the aligned table: surface, one column per repo, and a `*` on differing rows.

    Returns:
        The table as text, one line per surface under a header line.

    """
    table = [["", "surface", *repos]]
    table += [
        ["*" if differs(r) else "", r.surface, *[_cell(c) for c in r.cells]]
        for r in rows
    ]
    widths = [max(len(line[i]) for line in table) for i in range(len(table[0]))]
    return "\n".join(
        "  ".join(text.ljust(w) for text, w in zip(line, widths, strict=True)).rstrip()
        for line in table
    )


def main(argv: list[str] | None = None) -> int:
    """Read the named census files and print them side by side.

    Returns:
        0, or 2 when a file cannot be read or is not a schema-1 census (named on stderr).

    """
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("files", nargs="+", type=Path, help="one schema-1 census per repo")
    args = ap.parse_args(argv, namespace=Options())
    try:
        repos, rows = align([load(p) for p in args.files])
    except CensusError as exc:
        sys.stderr.write(f"side_by_side: {exc}\n")
        return BAD_INPUT
    sys.stdout.write(render(repos, rows) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
