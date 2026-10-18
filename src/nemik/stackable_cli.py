# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: nemik-stackable, which ready cards one `mikemol-commit --stack` can carry now.

    nemik-stackable REPO

Reads each ready card's declared manifest (exact files, `--update --manifest`, mtools:W1426) and
picks, in rank order, the cards whose manifests are pairwise disjoint and disjoint from the files
already staged in REPO. A card with no manifest is counted, never stacked.
"""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from rdflib import Graph

from nemik import history
from nemik.adapter import OSLC_CM, STATE
from nemik.check import default_root, survey
from nemik.drift import drift, ride_along
from nemik.rank import load_weights, rank
from nemik.stackable import generated_files, manifest, proposal_rows, propose, report

RIDE_ALONG_BAR = 2


def history_cited(repo_dir: Path) -> Callable[[str], list[str]]:
    """Bind a repo's git history as the source of a card's touched files (nemik:W611).

    Args:
        repo_dir: The repo's working directory.

    Returns:
        A function from a card's symbol to the files the commits citing it touched.

    """

    def cited(symbol: str) -> list[str]:
        return history.cited_files(repo_dir, symbol)

    return cited


def drifted(
    g: Graph, name: str, cited: Callable[[str], list[str]]
) -> list[tuple[str, list[str]]]:
    """Find the done cards of a repo whose commits touched files outside their manifest.

    Args:
        g: The merged queue graph.
        name: The repo.
        cited: Maps a symbol to the files its citing commits touched.

    Returns:
        (symbol, files outside the manifest) for each done card that declared a manifest and
        drifted from it, in symbol order.

    """
    prefix = f"urn:nemik:{name}/"
    found: list[tuple[str, list[str]]] = []
    for node in g.subjects(OSLC_CM.state, STATE["done"]):
        if not str(node).startswith(prefix):
            continue
        symbol = str(node)[len(prefix) :]
        planned = manifest(g, name, symbol)
        extra = drift(cited(symbol), planned) if planned else []
        if extra:
            found.append((symbol, extra))
    return sorted(found)


def drift_lines(
    g: Graph, name: str, cited: Callable[[str], list[str]], at_least: int
) -> list[str]:
    """Report how far each done card's commits strayed from its manifest (nemik:W611).

    Args:
        g: The merged queue graph.
        name: The repo.
        cited: Maps a symbol to the files its citing commits touched.
        at_least: How many cards must miss a kind of file before it is reported as riding along.

    Returns:
        One line per done card with a manifest and some drift, then one per ride-along kind.

    """
    drifts = drifted(g, name, cited)
    lines = [f"{symbol}: drift {' '.join(extra)}" for symbol, extra in drifts]
    for one, cards in ride_along([extra for _, extra in drifts], at_least):
        lines.append(f"ride-along: {one} missed by {cards} cards")
    return lines


def print_drift(g: Graph, repo: Path) -> None:
    """Print the drift of every done card in a repo, from its git history.

    Args:
        g: The merged queue graph.
        repo: The repo's working directory.

    """
    found = drift_lines(g, repo.name, history_cited(repo), RIDE_ALONG_BAR)
    sys.stdout.write("\n".join(found) + "\n")


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
    ap.add_argument(
        "--propose",
        action="store_true",
        help="draft a manifest for each ready card without one, for you to confirm",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="with --propose: [{symbol, manifest, size, wide}] for a writer to apply",
    )
    ap.add_argument(
        "--drift",
        action="store_true",
        help="files each done card's commits touched beyond its manifest (nemik:W611)",
    )
    args = ap.parse_args(argv)
    root: Path = args.root
    name: str = args.repo
    proposing: bool = args.propose
    as_json: bool = args.json
    drifting: bool = args.drift
    if g is None:
        g = Graph()
        for _, queue, _ in survey(root):
            if queue is not None:
                g += queue
    if drifting:
        print_drift(g, root / name)
        return
    rows: list[dict[str, object]] = rank(g, name, load_weights())
    if proposing:
        cited = {
            str(row["symbol"]): history.cited_files(root / name, str(row["symbol"]))
            for row in rows
        }
        known = history.tracked_files(root / name)
        if as_json:
            sys.stdout.write(
                json.dumps(proposal_rows(g, name, rows, cited, known), indent=1) + "\n"
            )
            return
        sys.stdout.write("\n".join(propose(g, name, rows, cited, known)) + "\n")
        return
    staged = history.staged_paths(root / name)
    listing = root / name / ".claude" / "generated.json"
    text = listing.read_text(encoding="utf-8") if listing.exists() else ""
    lines = report(g, name, rows, staged, generated_files(text))
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
