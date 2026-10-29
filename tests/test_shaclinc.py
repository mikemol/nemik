# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W400: validating only what a change touches gives exactly the full run's findings."""

from collections.abc import Callable
from pathlib import Path

import pytest
from rdflib import Graph, Literal
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import annotate
from nemik.check import QUEUE, shapes, workstream_files
from nemik.shaclinc import _results, findings

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _fleet() -> Graph:
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def _cards(g: Graph) -> list[Node]:
    return sorted(set(g.subjects(OSLC_CM.state, None)), key=str)


def _done(g: Graph) -> None:
    n = _cards(g)[0]
    g.remove((n, OSLC_CM.state, None))
    g.add((n, OSLC_CM.state, NEMIK.Done))


def _blocked(g: Graph) -> None:
    n = _cards(g)[-1]
    g.remove((n, OSLC_CM.state, None))
    g.add((n, OSLC_CM.state, NEMIK.Blocked))


def _bad_blocker(g: Graph) -> None:
    g.add((_cards(g)[1], NEMIK.blockedOn, Literal("operator")))


def _untitled(g: Graph) -> None:
    g.remove((_cards(g)[2], NEMIK.title, None))


EDITS: list[Callable[[Graph], None]] = [_done, _blocked, _bad_blocker, _untitled]


@pytest.mark.parametrize("edit", EDITS, ids=lambda e: e.__name__)
def test_incremental_equals_full_after_an_edit(edit: Callable[[Graph], None]) -> None:
    g, sh = _fleet(), shapes()
    key = f"test-{edit.__name__}"
    findings(key, g, sh)
    edit(g)
    inc = sorted(findings(key, g, sh))
    full = sorted((f, s, m) for f, rows in _results(g, sh).items() for s, m in rows)
    assert inc == full


def test_edits_in_sequence_stay_equal() -> None:
    g, sh = _fleet(), shapes()
    findings("test-sequence", g, sh)
    for edit in EDITS:
        edit(g)
        inc = sorted(findings("test-sequence", g, sh))
        full = sorted((f, s, m) for f, rows in _results(g, sh).items() for s, m in rows)
        assert inc == full, edit.__name__
