# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W483: rank.frontier through mtools' shared walker agrees with the old stored-state walk.

The old walk decided a card was open from its stored state (rank._open) and called a card a leaf
when nothing open in its repo fed it. The walker takes the same cone as plain nodes and edges with
realized = the stored state is done. For every open card of the fixture fleet taken as a goal, the
leaves (dG) and what they wait on outside (ddG) must be the same set, card for card.
"""

import re
from pathlib import Path

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import BASE, NEMIK, OSLC_CM
from nemik.rank import _open, _repo, frontier, ref_of
from nemik.serve import Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _old_frontier(g: Graph, goal: Node) -> tuple[set[Node], set[str]]:
    """rank.frontier as it was before W483, verbatim: the reference the walker must agree with."""
    repo = _repo(goal)
    seen, stack, leaves, outside = {goal}, [goal], set(), set()
    while stack:
        n = stack.pop()
        feeders = set(g.subjects(NEMIK.enables, n)) | {
            t
            for t in g.objects(n, NEMIK.waitsFor)
            if str(t).startswith(BASE) and "/" in str(t)[len(BASE) :]
        }
        local_open = set()
        for f in feeders:
            if not _open(g, f):
                continue
            if _repo(f) == repo:
                local_open.add(f)
            else:
                outside.add(ref_of(f))
        if not local_open:
            leaves.add(n)
            for lit in g.objects(n, NEMIK.blockedOn):
                if not re.fullmatch(r"W\d+", str(lit).strip()):
                    outside.add(str(lit))
        for f in local_open - seen:
            seen.add(f)
            stack.append(f)
    return leaves, outside


def test_the_walker_agrees_with_the_old_walk_on_every_open_card() -> None:
    """The walker agrees with the old walk on every open card."""
    model = Model(FLEET)
    model.refresh()
    g = model.graph
    goals = sorted(
        (n for n in set(g.subjects(OSLC_CM.state, None)) if _open(g, n)), key=str
    )
    assert len(goals) > 10, "the fixture fleet is too small to say anything"
    differ = [ref_of(n) for n in goals if frontier(g, n) != _old_frontier(g, n)]
    assert differ == []
