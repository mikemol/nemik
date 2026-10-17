# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: nemik-stackable, which ready cards one `mikemol-commit --stack` can carry now.

    nemik-stackable REPO

Reads each ready card's declared manifest (exact files, `--update --manifest`, mtools:W1426) and
picks, in rank order, the cards whose manifests are pairwise disjoint and disjoint from the files
already staged in REPO. A card with no manifest is counted, never stacked.
"""

import argparse
import sys
from pathlib import Path

from rdflib import Graph

from nemik import history
from nemik.check import default_root, survey
from nemik.rank import load_weights, rank
from nemik.stackable import report


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """Print the stackable set for a repo.

    Args:
        argv: The command line, or None for sys.argv.
        g: The merged queue graph, or None to read the fleet.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-stackable", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument("repo", help="the repo whose ready cards to stack")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    args = ap.parse_args(argv)
    root: Path = args.root
    name: str = args.repo
    if g is None:
        g = Graph()
        for _, queue, _ in survey(root):
            if queue is not None:
                g += queue
    rows: list[dict[str, object]] = rank(g, name, load_weights())
    staged = history.staged_paths(root / name)
    sys.stdout.write("\n".join(report(g, name, rows, staged)) + "\n")


if __name__ == "__main__":
    main()
