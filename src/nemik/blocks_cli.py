"""The `nemik-inbound` and `nemik-operator` commands, over the readings in `nemik.blocks`.

They live apart from `blocks` because they need `nemik.check.survey`, and `check` imports
`blocks.annotate`. Keeping the commands in `blocks` made the two modules import each other (a
lazy import hid it); a command sits above both, so the dependency runs one way.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import ledger_graph
from nemik.blocks import CATEGORIES, inbound, operator_asks
from nemik.check import LEDGER, default_root, survey, workstream_files


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-inbound [REPO]: what is waiting on REPO (or on everyone), and who claims it."""
    ap = argparse.ArgumentParser(
        prog="nemik-inbound", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("repo", nargs="?", help="only blocks on this workstream")
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    blocks = [
        b
        for b in inbound(g, letters=True)
        if not args.repo or b["blocker"] == args.repo
    ]
    if args.json:
        print(json.dumps(blocks, indent=2))
        return
    for b in blocks:
        claim = ", ".join(b["claimed_by"]) or "UNCLAIMED"
        # UNCLAIMED stays as the column token other repos' ticks read; the hint says whose move it is.
        hint = (
            ""
            if b["claimed_by"]
            else f"  -- waiting on you, claim with --enables {b['blocked']}"
        )
        # nemik:W275: the letter files the waiting waypoint cites as evidence, after the hint.
        letters = f"  [letter: {', '.join(b['letters'])}]" if b["letters"] else ""
        print(
            f"{b['blocker']:24} <- {b['blocked']:28} {claim:28} {b['title'][:60]}{hint}{letters}"
        )


def operator_main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-operator: blocks on the operator, sorted into needs-you / answered / condition / unstated."""
    ap = argparse.ArgumentParser(
        prog="nemik-operator", description=(operator_main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(root):
            if qg is not None:
                g += qg
        for repo, path in workstream_files(root, LEDGER):
            g += ledger_graph(repo, path)[0]
    from nemik.blocks import with_salience

    asks = with_salience(g, operator_asks(g))
    if args.json:
        print(json.dumps(asks, indent=2))
        return
    for cat in CATEGORIES:
        rows = [a for a in asks if a["category"] == cat]
        print(f"\n{cat} ({len(rows)}), heaviest first")
        for a in rows:
            dup = f"  same ask as {', '.join(a['same_ask'])}" if a["same_ask"] else ""
            behind = f"  <- {', '.join(a['waiting'])}" if a["waiting"] else ""
            # nemik:W298: the demand that waits behind the ask, in nemik-rank's units.
            weight = f"{a['salience']:6.1f}"
            print(f"  {weight} {a['ref']:28} {a['ask'][:70]}{dup}{behind}")
