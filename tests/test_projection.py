# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W413: the card-to-task projection keeps every blocking edge, and decodes back to them."""

from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import annotate, ref
from nemik.check import QUEUE, workstream_files
from nemik.projection import decode, project

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _fleet() -> Graph:
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def _edges(g: Graph) -> set[tuple[str, str]]:
    # Computed from the graph independently of nemik.projection: waits-for, and enables reversed.
    cards = set(g.subjects(OSLC_CM.state, None))
    waits = g.subject_objects(NEMIK.waitsFor)
    enables = g.subject_objects(NEMIK.enables)
    return {(ref(s), ref(o)) for s, o in waits if s in cards and o in cards} | {
        (ref(t), ref(s)) for s, t in enables if s in cards and t in cards
    }


def test_the_projection_decodes_to_every_blocking_edge() -> None:
    """The projection decodes to every blocking edge."""
    g = _fleet()
    tasks = project(g)
    assert tasks, "the fixture fleet has cards"
    assert _edges(g), "and blocking edges, so the round trip is not vacuous"
    assert decode(tasks) == _edges(g)


def test_uids_are_positive_unique_and_cross_repo_links_are_marked() -> None:
    """Uids are positive unique and cross repo links are marked."""
    tasks = project(_fleet())
    assert sorted(t.uid for t in tasks) == list(range(1, len(tasks) + 1))
    for t in tasks:
        for link in t.preds:
            assert link.cross_repo == (link.cite.partition(":")[0] != t.repo)


def test_one_repo_keeps_its_links_into_others() -> None:
    """One repo keeps its links into others."""
    g = _fleet()
    repo = project(g)[0].repo
    mine = project(g, {repo})
    assert {t.repo for t in mine} == {repo}
    assert decode(mine) == {(a, b) for a, b in _edges(g) if a.startswith(repo + ":")}
