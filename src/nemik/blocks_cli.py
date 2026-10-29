# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""The `nemik-inbound` and `nemik-operator` commands, over the readings in `nemik.blocks`.

They live apart from `blocks` because they need `nemik.check.survey`, and `check` imports
`blocks.annotate`. Keeping the commands in `blocks` made the two modules import each other (a
lazy import hid it); a command sits above both, so the dependency runs one way.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdflib import Graph

from nemik import tiers
from nemik.adapter import ledger_graph
from nemik.blocks import (
    CATEGORIES,
    inbound,
    operator_asks,
    sudo_shaped_asks,
    with_salience,
)
from nemik.check import LEDGER, default_root, survey, workstream_files
from nemik.inbound_issues import by_peer, census, letters_of, unclaimed
from nemik.letters import _split, _today, fold_commands
from nemik.rank import TIERS


def issue_letters(
    answer: Path, root: Path, repo: str, *, counts: bool, peers: bool = False
) -> None:
    """Print a repo's letters read from a recorded issues answer (nemik:W1169).

    Args:
        answer: The JSON an issues endpoint answered, saved to a file; nothing is fetched.
        root: ~/github, or the export layout root, where the repo's queue is read.
        repo: The repo whose queue claims the letters; empty reads no queue, so every open letter
            is unclaimed.
        counts: Print the census (sender, kind, open and closed counts) and not the UNCLAIMED rows.
        peers: With counts, group the census by sender alone (the per-peer comparison).

    """
    letters = letters_of(answer.read_text(encoding="utf-8"))
    if counts:
        lines = by_peer(letters) if peers else census(letters)
        sys.stdout.write("".join(f"{line}\n" for line in lines))
        return
    queue = root / repo / ".claude" / "paths-forward.json"
    text = queue.read_text(encoding="utf-8") if repo and queue.is_file() else ""
    for letter in unclaimed(letters, text):
        sender = letter["from"] or "-"
        sys.stdout.write(
            f"{repo or '-':24} <- issue {letter['url']:51} UNCLAIMED"
            f"  -- {letter['kind']} from {sender}: {letter['title']}\n"
        )


class _Operator(argparse.Namespace):
    """The arguments of nemik-operator, typed so reading them names no Any (nemik:W1265)."""

    root: Path
    json: bool
    sudo_shaped: bool


class _Inbound(argparse.Namespace):
    """The arguments of nemik-inbound, typed so reading them names no Any."""

    repo: str | None
    root: Path
    json: bool
    issues: Path | None
    census: bool
    by_peer: bool


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
    ap.add_argument(
        "--issues",
        type=Path,
        help="read letters from this saved issues answer (nemik:W1169) and print the open ones "
        "no waypoint of REPO cites; nothing is fetched",
    )
    ap.add_argument(
        "--census",
        action="store_true",
        help="with --issues: print the letters counted by sender and kind instead",
    )
    ap.add_argument(
        "--by-peer",
        action="store_true",
        help="with --census: group by sender alone, one line per peer",
    )
    args = ap.parse_args(argv, namespace=_Inbound())
    if args.issues is not None:
        issue_letters(
            args.issues,
            args.root,
            args.repo or "",
            counts=args.census,
            peers=args.by_peer,
        )
        return
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
        # UNCLAIMED stays as the column token other repos' ticks read; the hint says whose move it
        # is.
        hint = (
            ""
            if b["claimed_by"]
            else f"  -- waiting on you, claim with --enables {b['blocked']}"
        )
        # nemik:W275: the letter files the waiting waypoint cites as evidence, after the hint.
        letters = f"  [letter: {', '.join(b['letters'])}]" if b["letters"] else ""
        print(
            f"{b['blocker']:24} <- {b['blocked']:28} {claim:28} {b['title']}{hint}{letters}"
        )
    # nemik:W376: a letter in REPO's inbox that no waypoint cites is waiting on REPO too (one sat
    # two days unseen, luthen-observability:W722). The same UNCLAIMED token, with the --add that
    # claims it; the fold's 14-day cutoff leaves old ones to `nemik-check --letters --fold`.
    if args.repo:
        live = _split(Path(args.root), args.repo, 14, _today())[0]
        claims = fold_commands(Path(args.root), repo=args.repo, older_than=14)
        for (_, path), cmd in zip(live, claims, strict=True):
            print(
                f"{args.repo:24} <- letter {path.name:51} UNCLAIMED  -- claim with: {cmd}"
            )


def _report_sudo_shaped(g: Graph) -> None:
    """Print the flagged asks and exit 1 when there is one (nemik:W1265).

    Args:
        g: The fleet graph.

    """
    flagged = sudo_shaped_asks(g)
    for ref, ask in flagged:
        sys.stdout.write(f"{ref:28} {ask[:70]}\n")
    if flagged:
        sys.exit(1)


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
    ap.add_argument(
        "--sudo-shaped",
        action="store_true",
        help=(
            "print each 'operator: act' ask that names a root-shaped command and has no "
            "'apply loop cannot:' line in its evidence (nemik:W1265); exit 1 only when there is "
            "one, 0 otherwise, so a tick hook can read it without anything paging"
        ),
    )
    args = ap.parse_args(argv, namespace=_Operator())

    root = Path(args.root)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(root):
            if qg is not None:
                g += qg
        for repo, path in workstream_files(root, LEDGER):
            g += ledger_graph(repo, path)[0]
    if args.sudo_shaped:
        _report_sudo_shaped(g)
        return
    asks = with_salience(g, operator_asks(g))
    if args.json:
        print(json.dumps(asks, indent=2))
        return
    for cat in CATEGORIES:
        declared = TIERS
        # nemik:W600: grouped by the repo's burn-down tier, heaviest first inside a tier.
        rows = [asks[i] for i in tiers.order(asks, cat, declared)]
        # nemik:W458: an act ask with nothing to run is the owner's debt, not the operator's.
        label = {
            "no-command": "no command yet: the owner owes a tool",
            "errand": "errand: yours, no tool to write",
        }.get(cat, cat)
        print(f"\n{label} ({len(rows)}), heaviest first")
        for a in rows:
            dup = f"  same ask as {', '.join(a['same_ask'])}" if a["same_ask"] else ""
            behind = f"  <- {', '.join(a['waiting'])}" if a["waiting"] else ""
            # nemik:W298: the demand that waits behind the ask, in nemik-rank's units.
            weight = f"{a['salience']:6.1f}"
            print(f"  {weight} {a['ref']:28} {a['ask'][:70]}{dup}{behind}")
