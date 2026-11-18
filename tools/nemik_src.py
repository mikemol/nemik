# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2087: bazel/*.bzl name the python files of src/nemik and tests; this keeps them current.

The operator ruled the glob away (host line 152589): inputs are named, with names from
`git ls-files`. A sandboxed bazel test sees only the files BUILD names, so it cannot notice an
unnamed one; the comparison runs where git exists (the pre-commit hook, which feeds it
`git ls-files`). `--write` regenerates the lists, `--check` fails when one differs. Two lists:
src/nemik (NEMIK_PY, bazel/nemik_src.bzl) and tests (TESTS_PY, bazel/nemik_tests.bzl, nemik:W2261:
the guard that reads every test file by ast).
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]


class Spec(NamedTuple):
    """One generated list: the file, the tree it names, and the constant it defines."""

    list_file: str
    tree: str
    const: str
    summary: str


SRC_SPEC = Spec(
    "bazel/nemik_src.bzl",
    "src/nemik",
    "NEMIK_PY",
    "The python files of src/nemik, named (operator ruling 2026-11-08, host line 152589).",
)
TESTS_SPEC = Spec(
    "bazel/nemik_tests.bzl",
    "tests",
    "TESTS_PY",
    "The python files of tests, named (nemik:W2261, the same ruling as nemik_src.bzl).",
)
SPECS = (SRC_SPEC, TESTS_SPEC)
LIST_FILE = SRC_SPEC.list_file
SRC = SRC_SPEC.tree


class Options(argparse.Namespace):
    """The parsed command line of tools/nemik_src.py."""

    root: Path
    write: bool
    staged: bool


def header(spec: Spec) -> str:
    """Make the header of a list file.

    Returns:
        The docstring and the opening of the list.

    """
    return (
        f'"""{spec.summary}\n\n'
        f"Names come from `git ls-files {spec.tree}`, the .py files only. Adding or removing a\n"
        "file is a reviewed edit of this list. tools/nemik_src.py --write regenerates it and\n"
        '--check fails when it is stale (nemik:W2087).\n"""\n\n'
        f"{spec.const} = [\n"
    )


def render(tracked: list[str], spec: Spec = SRC_SPEC) -> str:
    """Make the text of the list file from the tracked paths.

    Args:
        tracked: Paths under the spec's tree, any kind; only python files are named.
        spec: Which list.

    Returns:
        The file text, names sorted.

    """
    names = sorted({p for p in tracked if p.endswith(".py")})
    return header(spec) + "".join(f'    "{n}",\n' for n in names) + "]\n"


def named_in(text: str, spec: Spec = SRC_SPEC) -> set[str]:
    """Read the names a list file holds.

    Args:
        text: The list file's text.
        spec: Which list.

    Returns:
        The named paths.

    """
    name = re.compile(rf'^\s*"({re.escape(spec.tree)}/[^"]+)",\s*$', re.MULTILINE)
    return {str(m.group(1)) for m in name.finditer(text)}


def compare(named: set[str], tracked: set[str]) -> tuple[list[str], list[str]]:
    """Say what the list lacks and what it names that is not tracked.

    Args:
        named: The names in the list file.
        tracked: The tracked python paths.

    Returns:
        (missing, extra), both sorted.

    """
    return sorted(tracked - named), sorted(named - tracked)


def check(text: str, tracked: list[str], spec: Spec = SRC_SPEC) -> list[str]:
    """Compare the list file with the tracked paths.

    Args:
        text: The list file's text.
        tracked: Paths under the spec's tree, any kind.
        spec: Which list.

    Returns:
        The problems; none when the file is exactly what render makes.

    """
    wanted = render(tracked, spec)
    if text == wanted:
        return []
    python = {p for p in tracked if p.endswith(".py")}
    missing, extra = compare(named_in(text, spec), python)
    have, want = text.splitlines(), wanted.splitlines()
    first = next(
        (i + 1 for i, (a, b) in enumerate(zip(have, want, strict=False)) if a != b),
        min(len(have), len(want)) + 1,
    )
    msg = (
        f"{spec.list_file} differs from git ls-files at line {first}: "
        f"missing {missing}, extra {extra}; run tools/nemik_src.py --write"
    )
    return [msg]


def tracked_paths(root: Path, spec: Spec = SRC_SPEC) -> list[str]:
    """List the tracked paths under the spec's tree.

    Args:
        root: The repository root.
        spec: Which list.

    Returns:
        The paths git reports.

    Raises:
        RuntimeError: git failed, so there is nothing to compare with.

    """
    shown = capture(["git", "-C", str(root), "ls-files", spec.tree])
    if shown.returncode != 0:
        msg = f"git ls-files failed: {shown.stderr.strip()}"
        raise RuntimeError(msg)
    return shown.stdout.splitlines()


def staged_text(root: Path, spec: Spec = SRC_SPEC) -> str:
    """Read the list file as the index holds it.

    Args:
        root: The repository root.
        spec: Which list.

    Returns:
        The staged text of the list file.

    Raises:
        RuntimeError: git could not show the staged file.

    """
    shown = capture(["git", "-C", str(root), "show", f":{spec.list_file}"])
    if shown.returncode != 0:
        msg = f"git show :{spec.list_file} failed: {shown.stderr.strip()}"
        raise RuntimeError(msg)
    return shown.stdout


def main(argv: list[str] | None = None) -> int:
    """Check the list files, or regenerate them.

    Args:
        argv: The command line.

    Returns:
        0 when every file is current, 1 otherwise.

    """
    ap = argparse.ArgumentParser(description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--write", action="store_true", help="regenerate the list files")
    ap.add_argument(
        "--staged", action="store_true", help="read the lists from the index"
    )
    args = ap.parse_args(argv, namespace=Options())
    problems: list[str] = []
    for spec in SPECS:
        tracked = tracked_paths(args.root, spec)
        target = args.root / spec.list_file
        if args.write:
            target.write_text(render(tracked, spec), encoding="utf-8")
        text = (
            staged_text(args.root, spec)
            if args.staged
            else target.read_text(encoding="utf-8")
        )
        problems += check(text, tracked, spec)
    for line in problems:
        sys.stdout.write(line + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
