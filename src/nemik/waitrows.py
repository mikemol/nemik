# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""waitrows: the graph's cross-repo wait edges as waitseries rows (nemik:W875, W836, W579).

waitseries groups rows into samples over plain data. This reads the rows out of the merged queue
graph: one per blocked card that waits on a card of another repo, as (waiting repo, blocking repo,
ticks the waiting card has been blocked). It uses only rdflib's typed calls (Graph.triples and
Graph.value), so it adds no untyped expression to the baselines.
"""

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM
from nemik.rank import ref_of
from nemik.waitseries import Row


def wait_rows(g: Graph) -> list[Row]:
    """Read a graph's cross-repo wait edges as rows.

    An edge counts when its waiter is blocked, its target is a card (not a workstream or the
    operator, which have no state) and the two cards are in different repos. A card that waits on
    two cards of another repo gives two rows, because each is a wait edge.

    Args:
        g: The merged queue graph.

    Returns:
        One (waiting repo, blocking repo, ticks blocked) per cross-repo wait edge, in no order.

    """
    rows: list[Row] = []
    for waiter, _, target in g.triples((None, NEMIK.waitsFor, None)):
        if g.value(waiter, OSLC_CM.state) != NEMIK.Blocked:
            continue
        if g.value(target, OSLC_CM.state) is None:
            continue
        waiting = ref_of(waiter).partition(":")[0]
        blocking = ref_of(target).partition(":")[0]
        if waiting == blocking:
            continue
        ticks = int(str(g.value(waiter, NEMIK.ticksBlocked) or 0))
        rows.append((waiting, blocking, ticks))
    return rows
