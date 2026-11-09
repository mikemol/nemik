# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2087: bazel/nemik_src.bzl names the python files of src/nemik, and this keeps it current.

The operator ruled the glob away (host line 152589): inputs are named, with names from
`git ls-files`. A sandboxed bazel test sees only the files BUILD names, so it cannot notice an
unnamed one; the comparison runs where git exists (the pre-commit hook, which feeds it
`git ls-files src/nemik`). `--write` regenerates the list, `--check` fails when it differs.
"""

import argparse
import re
import sys
from pathlib import Path

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]
LIST_FILE = "bazel/nemik_src.bzl"
SRC = "src/nemik"
HEADER = '''"""The python files of src/nemik, named (operator ruling 2026-11-08, host line 152589).

Names come from `git ls-files src/nemik`, the .py files only. Adding or removing a module is a
reviewed edit of this list. tools/nemik_src.py --write regenerates it and --check fails when it is
stale (nemik:W2087).
"""

NEMIK_PY = [
'''
NAME = re.compile(r'^\s*"(src/nemik/[^"]+)",\s*$', re.MULTILINE)


class Options(argparse.Namespace):
    """The parsed command line of tools/nemik_src.py."""

    root: Path
    write: bool
    staged: bool


def render(tracked: list[str]) -> str:
    """Make the text of the list file from the tracked paths.

    Args:
        tracked: Paths under src/nemik, any kind; only python files are named.

    Returns:
        The file text, names sorted.

    """
    names = sorted({p for p in tracked if p.endswith(".py")})
    return HEADER + "".join(f'    "{n}",\n' for n in names) + "]\n"


def named_in(text: str) -> set[str]:
    """Read the names a list file holds.

    Args:
        text: The list file's text.

    Returns:
        The named paths.

    """
    return {str(m.group(1)) for m in NAME.finditer(text)}


def compare(named: set[str], tracked: set[str]) -> tuple[list[str], list[str]]:
    """Say what the list lacks and what it names that is not tracked.

    Args:
        named: The names in the list file.
        tracked: The tracked python paths.

    Returns:
        (missing, extra), both sorted.

    """
    return sorted(tracked - named), sorted(named - tracked)


def check(text: str, tracked: list[str]) -> list[str]:
    """Compare the list file with the tracked paths.

    Args:
        text: The list file's text.
        tracked: Paths under src/nemik, any kind.

    Returns:
        The problems; none when the file is exactly what render makes.

    """
    wanted = render(tracked)
    if text == wanted:
        return []
    python = {p for p in tracked if p.endswith(".py")}
    missing, extra = compare(named_in(text), python)
    have, want = text.splitlines(), wanted.splitlines()
    first = next(
        (i + 1 for i, (a, b) in enumerate(zip(have, want, strict=False)) if a != b),
        min(len(have), len(want)) + 1,
    )
    msg = (
        f"{LIST_FILE} differs from git ls-files at line {first}: "
        f"missing {missing}, extra {extra}; run tools/nemik_src.py --write"
    )
    return [msg]


def tracked_paths(root: Path) -> list[str]:
    """List the tracked paths under src/nemik.

    Args:
        root: The repository root.

    Returns:
        The paths git reports.

    Raises:
        RuntimeError: git failed, so there is nothing to compare with.

    """
    shown = capture(["git", "-C", str(root), "ls-files", SRC])
    if shown.returncode != 0:
        msg = f"git ls-files failed: {shown.stderr.strip()}"
        raise RuntimeError(msg)
    return shown.stdout.splitlines()


def staged_text(root: Path) -> str:
    """Read the list file as the index holds it.

    Args:
        root: The repository root.

    Returns:
        The staged text of the list file.

    Raises:
        RuntimeError: git could not show the staged file.

    """
    shown = capture(["git", "-C", str(root), "show", f":{LIST_FILE}"])
    if shown.returncode != 0:
        msg = f"git show :{LIST_FILE} failed: {shown.stderr.strip()}"
        raise RuntimeError(msg)
    return shown.stdout


def main(argv: list[str] | None = None) -> int:
    """Check the list file, or regenerate it.

    Args:
        argv: The command line.

    Returns:
        0 when the file is current, 1 otherwise.

    """
    ap = argparse.ArgumentParser(description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--write", action="store_true", help="regenerate the list file")
    ap.add_argument(
        "--staged", action="store_true", help="read the list from the index"
    )
    args = ap.parse_args(argv, namespace=Options())
    tracked = tracked_paths(args.root)
    target = args.root / LIST_FILE
    if args.write:
        target.write_text(render(tracked), encoding="utf-8")
    text = staged_text(args.root) if args.staged else target.read_text(encoding="utf-8")
    problems = check(text, tracked)
    for line in problems:
        sys.stdout.write(line + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
