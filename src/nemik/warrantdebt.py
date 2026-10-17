# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W608: the warrant debt may only fall.

A card whose prose claims an operator ruling without a warrant (nemik:W597) is warrant debt. The
fleet carried 72 such cards when the debt was first counted; the baseline in rank-weights.toml
under [warrant_debt] holds each repo's count at that moment, and nemik-check warns on a repo whose
live count is above it. A Warning, not a gate: the count reads the other repos' live queues, which
a commit in this repo does not control. Lower a repo's number in the same change that warrants its
cards; a repo absent from the table has a baseline of zero.
"""

import tomllib
from collections import Counter
from importlib.resources import files

from rdflib import Graph

from nemik.adapter import NEMIK
from nemik.blocks import ref


def baseline(text: str | None = None) -> dict[str, int]:
    """Read each repo's declared warrant-debt ceiling.

    Args:
        text: The rank-weights TOML, or None for the one that ships with the package.

    Returns:
        The ceiling by repo; empty when the table is absent.

    """
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    document: dict[str, object] = tomllib.loads(text)
    table = document.get("warrant_debt")
    found: dict[str, int] = {}
    if isinstance(table, dict):
        for repo, count in table.items():
            if isinstance(count, int):
                found[str(repo)] = count
    return found


def debt(merged: Graph) -> Counter[str]:
    """Count each repo's open cards that claim a ruling with no warrant.

    Args:
        merged: The merged queue graph.

    Returns:
        The count by repo.

    """
    return Counter(
        ref(node).partition(":")[0]
        for node in merged.subjects(NEMIK.claimsRuling, None)
    )


def findings(merged: Graph, ceilings: dict[str, int]) -> dict[str, str]:
    """Name each repo whose warrant debt is above its ceiling.

    Args:
        merged: The merged queue graph.
        ceilings: The declared ceiling by repo (see baseline).

    Returns:
        The warning text per repo.

    """
    found: dict[str, str] = {}
    for repo, count in sorted(debt(merged).items()):
        ceiling = ceilings.get(repo, 0)
        if count > ceiling:
            found[repo] = (
                f"{count} open cards claim an operator ruling with no warrant, above the "
                f"declared {ceiling} ([warrant_debt] in rank-weights.toml): attach a warrant "
                "(--warrant SYMBOL --transcript PATH --uuid UUID) or drop the claim"
            )
    return found
