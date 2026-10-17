# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: which ready cards can be committed together as one stack.

A stack is several commits gated once, so its entries must not share a file. Each ready card
declares a manifest of exact repo-relative files it will create or edit (nemik:W612; never a
directory or a glob). Two cards overlap when their manifests share a file. The pick is greedy in
rank order: a card joins when it overlaps neither a card already picked nor a file in flight.
Greedy is not the maximum set of disjoint cards (a maximum independent set, NP-hard), but it is
how a stack is built by hand, it keeps the highest-ranked cards, and it is linear in the manifests.
"""

from rdflib import Graph

from nemik.adapter import NEMIK, waypoint_uri


def manifest(g: Graph, repo: str, symbol: str) -> list[str]:
    """Read a card's declared manifest from the graph.

    Args:
        g: The merged queue graph.
        repo: The card's repo.
        symbol: The card's symbol.

    Returns:
        Its planned files, sorted; empty when it declares none.

    """
    node = waypoint_uri(repo, symbol)
    return sorted(str(path) for path in g.objects(node, NEMIK.plannedPath))


def report(
    g: Graph, repo: str, ranked: list[dict[str, object]], in_flight: list[str]
) -> list[str]:
    """Describe the stack the repo's ready cards can make now.

    Args:
        g: The merged queue graph.
        repo: The repo's name.
        ranked: The repo's ready cards in rank order (nemik.rank.rank rows).
        in_flight: Files already staged.

    Returns:
        One line per planned card (STACK when it joins, WAITING when a file overlaps), then a total
        with the count of cards that have no manifest.

    """
    cards = [f"{repo}:{row['symbol']}" for row in ranked]
    plans = [manifest(g, repo, str(row["symbol"])) for row in ranked]
    chosen = set(pick(cards, plans, in_flight))
    out = [
        f"{'STACK  ' if cite in chosen else 'WAITING'} {cite}  {' '.join(files)}"
        for cite, files in zip(cards, plans, strict=True)
        if files
    ]
    unplanned = sum(1 for files in plans if not files)
    out.append(
        f"{len(chosen)} stackable of {len(cards)} ready; {unplanned} have no manifest"
    )
    return out


def pick(
    cards: list[str], manifests: list[list[str]], in_flight: list[str]
) -> list[str]:
    """Pick the cards that can stack, most urgent first.

    Args:
        cards: The ready cards' citations, in rank order.
        manifests: Each card's planned files, parallel to `cards`; an empty manifest is a card that
            is not planned, which never stacks.
        in_flight: Files already staged or in a gate.

    Returns:
        The citations that are pairwise disjoint and disjoint from `in_flight`, in rank order.

    """
    taken = set(in_flight)
    chosen: list[str] = []
    for cite, files in zip(cards, manifests, strict=True):
        if not files or taken.intersection(files):
            continue
        chosen.append(cite)
        taken.update(files)
    return chosen
