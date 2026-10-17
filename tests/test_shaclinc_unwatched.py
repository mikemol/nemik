# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W637: a change to a predicate no shape reads re-judges nothing."""

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.term import Node

from nemik.adapter import BASE, NEMIK
from nemik.check import shapes
from nemik.shaclinc import Result, findings, watched_predicates


def test_the_real_shapes_do_not_read_queue_position() -> None:
    """Display order (queuePosition) is named by no shape, so it is not watched."""
    watched = watched_predicates(shapes(), [])
    assert "queuePosition" not in watched
    assert "blockedOn" in watched


def test_a_variable_predicate_makes_every_predicate_count() -> None:
    """A query that reads `?s ?p ?o` may read any predicate: nothing is unwatched."""
    watched = watched_predicates(shapes(), ["SELECT $this WHERE { $this ?p ?o }"])
    assert "?" in watched


def test_changing_an_unwatched_predicate_runs_no_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two runs differing only in queuePosition: the second validates nothing."""
    calls: list[int] = []

    def counted(data: Graph, shapes_graph: Graph) -> dict[Node, list[Result]]:
        calls.append(len(data) + len(shapes_graph))
        return {}

    monkeypatch.setattr("nemik.shaclinc._results", counted)
    card = URIRef(f"{BASE}unwatched-test/W1")
    first = Graph()
    first.add((card, NEMIK.queuePosition, Literal(1)))
    second = Graph()
    second.add((card, NEMIK.queuePosition, Literal(2)))
    findings("unwatched-key", first, shapes())
    assert len(calls) == 1
    findings("unwatched-key", second, shapes())
    assert len(calls) == 1
