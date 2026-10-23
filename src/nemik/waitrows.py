# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""waitrows: the graph's cross-repo wait edges as waitseries rows (nemik:W875, W883, W836, W579).

waitseries groups rows into samples over plain data. This reads the rows out of the merged queue
graph: one per blocked card that waits on a card of another repo, as (waiting repo, blocking repo,
ticks the waiting card has been blocked), and the same edges with the blocker's rank position. It
uses only rdflib's typed calls (Graph.triples and Graph.value) and rank.rank_fleet, whose rows are
typed, so it adds no untyped expression to the baselines.
"""

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM
from nemik.rank import Weights, rank_fleet, ref_of
from nemik.waitseries import Row

# (waiting repo, blocking repo, ticks blocked, the blocker's rank position; 0 when it is not ranked)
Edge = tuple[str, str, int, int]
# (waiting repo, blocking repo, ticks blocked, the waiting card's cite, the blocker's cite)
Oldest = tuple[str, str, int, str, str]
UNRANKED = 0


def _cross_repo(g: Graph) -> list[tuple[str, str, int, str, str]]:
    """Read a graph's cross-repo wait edges, each with the cites of both cards.

    An edge counts when its waiter is blocked, its target is a card (not a workstream or the
    operator, which have no state) and the two cards are in different repos. A card that waits on
    two cards of another repo gives two edges.

    Args:
        g: The merged queue graph.

    Returns:
        (waiting repo, blocking repo, ticks blocked, blocker's `repo:W<n>`, waiter's `repo:W<n>`),
        in no order.

    """
    out: list[tuple[str, str, int, str, str]] = []
    for waiter, _, target in g.triples((None, NEMIK.waitsFor, None)):
        if g.value(waiter, OSLC_CM.state) != NEMIK.Blocked:
            continue
        if g.value(target, OSLC_CM.state) is None:
            continue
        waiting_cite = ref_of(waiter)
        waiting = waiting_cite.partition(":")[0]
        cite = ref_of(target)
        blocking = cite.partition(":")[0]
        if waiting == blocking:
            continue
        ticks = int(str(g.value(waiter, NEMIK.ticksBlocked) or 0))
        out.append((waiting, blocking, ticks, cite, waiting_cite))
    return out


def wait_rows(g: Graph) -> list[Row]:
    """Read a graph's cross-repo wait edges as waitseries rows.

    Args:
        g: The merged queue graph.

    Returns:
        One (waiting repo, blocking repo, ticks blocked) per cross-repo wait edge, in no order.

    """
    return [
        (waiting, blocking, ticks) for waiting, blocking, ticks, _, _ in _cross_repo(g)
    ]


def blocker_positions(g: Graph, weights: Weights) -> dict[str, int]:
    """Rank the fleet's ready cards from 1, as nemik-rank --all lists them.

    Only a ready leaf is ranked; a card that is blocked, done or an umbrella has no position.

    Args:
        g: The merged queue graph.
        weights: The edge weights rank_fleet composes with.

    Returns:
        `repo:W<n>` -> its place in the fleet order.

    """
    out: dict[str, int] = {}
    for place, entry in enumerate(rank_fleet(g, weights), start=1):
        out[str(entry["cite"])] = place
    return out


def wait_edges(g: Graph, weights: Weights) -> list[Edge]:
    """Read the cross-repo wait edges with each blocker's rank position (nemik:W883).

    Args:
        g: The merged queue graph.
        weights: The edge weights rank_fleet composes with.

    Returns:
        One (waiting repo, blocking repo, ticks blocked, blocker position) per edge, the position
        UNRANKED (0) when the blocker is not a ready leaf; in no order.

    """
    place = blocker_positions(g, weights)
    return [
        (waiting, blocking, ticks, place.get(cite, UNRANKED))
        for waiting, blocking, ticks, cite, _ in _cross_repo(g)
    ]


def oldest_waits(g: Graph) -> list[Oldest]:
    """Name, per pair of repos, the card that has waited longest and the card it waits on.

    Card symbols are for log records only; a metric label never carries one (nemik:W886).

    Args:
        g: The merged queue graph.

    Returns:
        One (waiting repo, blocking repo, ticks blocked, waiting cite, blocker cite) per pair, the
        longest wait of that pair, ties to the smaller cites; ordered by the pair.

    """
    best: dict[tuple[str, str], Oldest] = {}
    for waiting, blocking, ticks, cite, waiting_cite in _cross_repo(g):
        pair = (waiting, blocking)
        row = (waiting, blocking, ticks, waiting_cite, cite)
        have = best.get(pair)
        if have is None or (-ticks, waiting_cite, cite) < (-have[2], have[3], have[4]):
            best[pair] = row
    return [best[pair] for pair in sorted(best)]
