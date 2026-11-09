# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2088: a registered ratchet may RISE only with a declared rebaseline, checked at the gate.

`mikemol-ratchet rebaselines --repo A --before B` refuses a rise with no `rebaselines.json` entry,
and nothing in nemik called it: `mikemol-pycheck --ratchet` compares ruff and mypy findings with the
tree's own baseline file, and the Codon census test compares with the tree's own file too, so a
change that adds a finding together with the matching baseline entry passed. This tool builds the
BEFORE tree from the HEAD commit (only the ratchet files and the declaration, read with git) and
runs the check on the staged tree against it. It fails closed: a git failure, an unreadable HEAD
or a tool that cannot run is a refusal, never a pass.

TWO HOLES IN THE CHECK ITSELF, closed here (github-14's cold review, B1 and B2), and to be closed in
mtools' rebaseline.check so this wrapper can shrink to the call:
- RETIRING A DECLARATION HIDES A RISE: the census reads only the rows ratchets.json declares and the
  refusals loop runs over the staged rows, so a stage that drops a row and raises the file passes.
  A path declared at HEAD that the staged declaration no longer declares is refused (status 1).
- AN UNREADABLE STAGED VALUE PASSES: a row whose staged value is None is skipped. Any such row is
  "could not judge" (status 7).

    python3 tools/rebaselines_gate.py --root REAL_ROOT --head SHA --tree STAGED_TREE
"""

import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import cast

from mikemol.procrun.proc import capture, capture_bytes
from mikemol.ratchet import rebaseline
from mikemol.ratchet.kinds import kind_of

DECLARATION = "ratchets.json"
REBASELINES = "rebaselines.json"
FAILED = 1
UNJUDGED = 7


class Options(argparse.Namespace):
    """The parsed command line of tools/rebaselines_gate.py."""

    root: Path
    head: str
    tree: Path


def _object(value: object) -> dict[str, object]:
    # The JSON object a value is, or an empty one: nothing declared reads as nothing.
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def declared_in(text: str) -> set[str]:
    """Read the ratchet files a ratchets.json text declares.

    Args:
        text: The declaration's text.

    Returns:
        The declared paths; none when the text is not a declaration.

    """
    try:
        parsed: object = json.loads(text)
    except ValueError:
        return set()
    rows = _object(parsed).get("ratchets")
    out: set[str] = set()
    for row in cast("list[object]", rows) if isinstance(rows, list) else []:
        path = _object(row).get("path")
        if isinstance(path, str):
            out.add(path)
    return out


def declared_paths(root: Path, head: str) -> set[str]:
    """Read the ratchet files ratchets.json declares at HEAD.

    Args:
        root: The repository root.
        head: The commit.

    Returns:
        The declared paths; none when HEAD has no declaration.

    """
    shown = capture(["git", "-C", str(root), "show", f"{head}:{DECLARATION}"])
    return declared_in(shown.stdout) if shown.returncode == 0 else set()


def retired(root: Path, head: str, tree: Path) -> list[str]:
    """List the paths declared at HEAD that the staged declaration no longer declares.

    Args:
        root: The repository root.
        head: The commit.
        tree: The staged tree.

    Returns:
        The dropped paths, sorted. There is no tombstone form yet, so none is excused.

    """
    declaration = tree / DECLARATION
    now: set[str] = set()
    if declaration.is_file():
        now = declared_in(declaration.read_text(encoding="utf-8"))
    return sorted(declared_paths(root, head) - now)


def unreadable(tree: Path) -> list[str]:
    """List the ratchet files of the staged tree whose value cannot be read.

    Args:
        tree: The staged tree.

    Returns:
        The paths whose value is None (corrupt JSON, a wrong shape), sorted.

    """
    rows = rebaseline.values(tree)
    return sorted(path for path, value in rows.items() if value is None)


def ratchet_files(root: Path, head: str) -> list[str]:
    """List the files at HEAD that hold ratchet state or its declaration.

    Args:
        root: The repository root.
        head: The commit.

    Returns:
        The paths: files of a ratchet kind, the declaration, the rebaselines and declared paths.

    Raises:
        RuntimeError: git could not list HEAD, so nothing can be compared.

    """
    listed = capture(["git", "-C", str(root), "ls-tree", "-r", "--name-only", head])
    if listed.returncode != 0:
        msg = f"git ls-tree failed: {listed.stderr.strip()}"
        raise RuntimeError(msg)
    declared = declared_paths(root, head)
    keep = {DECLARATION, REBASELINES}
    return [
        name
        for name in listed.stdout.splitlines()
        if name in declared or Path(name).name in keep or kind_of(Path(name).name)
    ]


def build_before(root: Path, head: str, target: Path) -> None:
    """Extract the ratchet files of HEAD into a directory.

    Args:
        root: The repository root.
        head: The commit.
        target: An empty directory.

    Raises:
        RuntimeError: git could not archive them.

    """
    names = ratchet_files(root, head)
    if not names:
        return
    argv = ["git", "-C", str(root), "archive", "--format=tar", head, "--", *names]
    done = capture_bytes(argv)
    if done.returncode != 0:
        msg = f"git archive failed: {done.stderr.decode(errors='replace').strip()}"
        raise RuntimeError(msg)
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
        archive.extractall(target, filter="data")


def main(argv: list[str] | None = None) -> int:
    """Check that the staged tree's ratchets rose only with declared rebaselines.

    Args:
        argv: The command line.

    Returns:
        0 when every rise is declared, 1 on a refusal, 7 when the check could not be made.

    """
    ap = argparse.ArgumentParser(description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--tree", type=Path, required=True)
    args = ap.parse_args(argv, namespace=Options())
    with tempfile.TemporaryDirectory() as tmp:
        before = Path(tmp)
        try:
            build_before(args.root, args.head, before)
        except RuntimeError as err:
            sys.stdout.write(f"rebaselines_gate: could not judge: {err}\n")
            return UNJUDGED
        dropped = retired(args.root, args.head, args.tree)
        if dropped:
            msg = f"declared at HEAD, no longer declared: {dropped}"
            sys.stdout.write(f"rebaselines_gate: {msg}\n")
            return FAILED
        bad = unreadable(args.tree)
        if bad:
            msg = f"could not judge: unreadable value in {bad}"
            sys.stdout.write(f"rebaselines_gate: {msg}\n")
            return UNJUDGED
        check = [sys.executable, "-m", "mikemol.ratchet.cli", "rebaselines"]
        check += ["--repo", str(args.tree), "--before", str(before)]
        done = capture(check)
    out = done.stdout + done.stderr
    sys.stdout.write(out)
    if done.returncode == 0:
        return 0
    if done.returncode == FAILED and "rebaselines" in out:
        return FAILED
    sys.stdout.write(
        "rebaselines_gate: could not judge: the check did not run to a verdict\n"
    )
    return UNJUDGED


if __name__ == "__main__":
    raise SystemExit(main())
