# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Fleet-wide touches[] overlap (nemik:W53), in the shape of mtools' `--overlaps` (mtools:W118).

`OVERLAP <tag>: <repo>:W<a>,<repo>:W<b>` for each tag that two or more live (ready or working)
waypoints share. `--cross` keeps only tags shared across repos: the part a single queue's own
`--overlaps` cannot see. Advisory, like ATOMIZE: always exits 0.

nemik:W305 (mtools:W913): a session working a card holds a fence claim
`claim:label:touch:<repo>:<tag>` per touches tag (mtools' mikemol-hook-work-claims). Each OVERLAP
row also names who holds the claim for its tag and how old it is, read from `mikemol-membudget
claims`. Display only: no block; with no membudget the holder column is left out, and said once.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, STATE
from nemik.blocks import _repo, ref

if TYPE_CHECKING:
    from rdflib.term import Node

LIVE = {STATE["ready"], STATE["working"]}
CLAIM = "claim:label:touch:"
DEFAULT_MEMBUDGET = (
    Path.home() / "github/mtools/bazel-bin/fence/.venv/bin/mikemol-membudget"
)


class Holder(NamedTuple):
    """Who holds a touched surface and how long it has been held."""

    owner: str
    age: str


def overlaps(g: Graph, cross: bool = False) -> dict[str, list[str]]:
    """Find the touched surfaces that more than one live card names.

    Returns:
        Each such surface tag with the cards that touch it.

    """
    by_tag: dict[str, set[Node]] = {}
    for node, tag in g.subject_objects(NEMIK.touches):
        if g.value(node, OSLC_CM.state) in LIVE:
            by_tag.setdefault(str(tag), set()).add(node)
    out: dict[str, list[str]] = {}
    for name, nodes in sorted(by_tag.items()):
        if len(nodes) < 2 or (cross and len({_repo(n) for n in nodes}) < 2):
            continue
        out[name] = sorted(ref(n) for n in nodes)
    return out


def parse_claims(text: str) -> dict[tuple[str, str], Holder]:
    """{(repo, tag): Holder} from `mikemol-membudget claims` lines.

    Each line reads `claim:label:touch:<repo>:<tag> owner=<pid:start> id=<id> age=<n>s`.
    """
    held: dict[tuple[str, str], Holder] = {}
    for line in text.splitlines():
        label, _, rest = line.strip().partition(" ")
        if not label.startswith(CLAIM):
            continue
        repo, _, tag = label.removeprefix(CLAIM).partition(":")
        fields = dict(f.split("=", 1) for f in rest.split() if "=" in f)
        held[repo, tag] = Holder(fields.get("owner", "?"), fields.get("age", "?"))
    return held


def read_claims(membudget: Path | None = None) -> dict[tuple[str, str], Holder] | None:
    """Read the live work claims, or None when mikemol-membudget cannot be run.

    $NEMIK_MEMBUDGET names the binary; otherwise mtools' fence venv is tried.
    """
    path = membudget or Path(os.environ.get("NEMIK_MEMBUDGET") or DEFAULT_MEMBUDGET)
    try:
        run = subprocess.run(
            [str(path), "claims"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return parse_claims(run.stdout) if run.returncode == 0 else None


def row(
    tag: str, refs: list[str], held: dict[tuple[str, str], Holder] | None = None
) -> str:
    """One OVERLAP line, with the claim holder of each ref's repo for this tag appended."""
    line = f"OVERLAP {tag}: {','.join(refs)}"
    owners = [
        f"{repo} held by {h.owner} ({h.age})"
        for repo in sorted({r.partition(":")[0] for r in refs})
        if held and (h := held.get((repo, tag)))
    ]
    return f"{line}  [{'; '.join(owners)}]" if owners else line


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """Print the tags that more than one open waypoint touches, with who holds a claim on each.

    Builds the graph from the survey of --root unless one is passed; --cross keeps only tags
    shared across repos. When there are overlaps but mikemol-membudget is unavailable it says so
    first and prints the rows without owners.

    Args:
        argv: the command line, or None for sys.argv.
        g: a graph to read instead of surveying the root.

    """
    import argparse

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument(
        "--cross", action="store_true", help="only tags shared across repos"
    )

    class Opts(argparse.Namespace):
        root: Path
        cross: bool

    args = ap.parse_args(argv, namespace=Opts())
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    found = overlaps(g, args.cross)
    held = read_claims() if found else None
    if found and held is None:
        print("(no claim holders: mikemol-membudget is not available)")
    for tag, refs in found.items():
        print(row(tag, refs, held))
