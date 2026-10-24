# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W587: nemik-ask, file an ask: mint the filer's waypoint, then write the entry citing it.

    nemik-ask --filer life --to mtools --slug ask-x-does-y --claim "x does not do y"     (dry run)
    nemik-ask --filer life --to mtools --slug ask-x-does-y --claim "..." --apply

The waypoint is minted in the FILER's queue through the one writer (`mikemol-paths-forward --add`,
then blocked on the owner), never by editing the file. Only then is the entry written to the floor
inbox with `waypoint = {<filer>:W<n>}`, because summit's place_intake refuses a pointer to a card
that is absent. The result is checked: the entry must be on the floor after writing.

nemik:W943: after filing, the same ask is printed as an ActivityStreams Offer addressed to the
owner (nemik.ask.offer), so a peer outside summit's tooling can read it. Nothing else is written:
summit's inbox takes bib letters only.
"""

import argparse
import sys
from pathlib import Path

from nemik.ask import blocked_on, braces_balanced, entry, offer, slug_ok, title
from nemik.work import run_writer

DEFAULT_FLOOR = Path.home() / "github" / "summit" / "floor" / "inbox"


def _refusal(slug: str, claim: str, target: Path) -> str:
    """Say what is wrong with the request, or nothing.

    Args:
        slug: The proposed key.
        claim: The ask's text.
        target: The floor file it would be written to.

    Returns:
        A one-line reason, empty when the request is fine.

    """
    if not slug_ok(slug):
        return f"slug {slug!r} must be lowercase letters, digits and hyphens"
    if not claim.strip():
        return "the claim is empty"
    if not braces_balanced(claim):
        return "the claim's braces do not balance, so it cannot sit in a BibTeX field"
    if target.exists():
        return (
            f"{target} already exists: pick another slug, never overwrite a filed ask"
        )
    return ""


def _parser() -> argparse.ArgumentParser:
    """Build the command line.

    Returns:
        The parser.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-ask", description="file an ask as a waypoint and an entry"
    )
    ap.add_argument("--filer", required=True, help="the repo filing the ask")
    ap.add_argument("--to", required=True, help="the repo it is addressed to")
    ap.add_argument("--slug", required=True, help="the entry key and file name stem")
    ap.add_argument("--claim", required=True, help="the ask's text")
    ap.add_argument(
        "--owner-card", default="", help="the owner's card that answers it, W<n>"
    )
    ap.add_argument("--state", type=Path, default=Path(".claude/paths-forward.json"))
    ap.add_argument(
        "--floor", type=Path, default=DEFAULT_FLOOR, help="summit's floor/inbox"
    )
    ap.add_argument(
        "--apply", action="store_true", help="mint and write; default is a dry run"
    )
    return ap


def _mint(state: Path, card_title: str, wait: str) -> tuple[int, str]:
    """Mint the filer's waypoint through the writer and block it on the owner.

    Args:
        state: The filer's queue file.
        card_title: The waypoint's title.
        wait: What it waits on.

    Returns:
        (0, the new symbol) on success, else (a non-zero status, why).

    """
    code, said = run_writer(["--state", str(state), "--add", card_title])
    symbol = said.split()[0] if said.split() else ""
    if code or not symbol.startswith("W"):
        return code or 1, f"the writer did not mint a card: {said}"
    block = ["--state", str(state), "--update", symbol, "--status", "blocked"]
    code, said = run_writer([*block, "--blocked-on", wait, "--blocked-kind", "agent"])
    if code:
        return code, f"{symbol} was minted but not blocked: {said}"
    return 0, symbol


def main(argv: list[str] | None = None) -> int:
    """File an ask: mint the filer's waypoint, then write the floor entry.

    Args:
        argv: The arguments, or None for the process's own.

    Returns:
        0 on success (or a dry run), 2 on a refused request, the writer's status if it failed.

    """
    args = _parser().parse_args(argv)
    filer: str = args.filer
    owner: str = args.to
    slug: str = args.slug
    claim: str = args.claim
    state: Path = args.state
    owner_card: str = args.owner_card
    apply: bool = args.apply
    floor: Path = args.floor
    target = floor / f"{slug}.bib"
    reason = _refusal(slug, claim, target)
    if reason:
        sys.stderr.write(f"nemik-ask: {reason}\n")
        return 2
    wait = blocked_on(owner, owner_card)
    if not apply:
        sys.stdout.write(
            f"would mint in {state}: {title(owner, claim)!r}, blocked on {wait}\n"
            f"would write {target}:\n{entry(slug, filer, owner, claim, 'W?')}"
        )
        return 0
    code, symbol = _mint(state, title(owner, claim), wait)
    if code:
        sys.stderr.write(f"nemik-ask: {symbol}\n")
        return code
    target.write_text(entry(slug, filer, owner, claim, symbol), encoding="utf-8")
    if not target.exists():
        sys.stderr.write(f"nemik-ask: {target} is not there after writing\n")
        return 1
    sys.stdout.write(f"filed {filer}:{symbol} blocked on {wait}; entry {target}\n")
    sys.stdout.write(offer(slug, filer, owner, claim, symbol))
    return 0
