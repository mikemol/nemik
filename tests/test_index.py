# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W412: inside a build the per-card facts come from one index, and they equal the graph's."""

from __future__ import annotations

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, waypoint_uri
from nemik.critical import _open as open_set
from nemik.index import index, indexed
from nemik.rank import _open, successors


def _graph() -> Graph:
    g = Graph()
    a, b, c = (waypoint_uri("r", s) for s in ("W1", "W2", "W3"))
    g.add((a, OSLC_CM.state, NEMIK.Ready))
    g.add((b, OSLC_CM.state, NEMIK.Blocked))
    g.add((c, OSLC_CM.state, NEMIK.Done))
    g.add((a, NEMIK.enables, b))
    g.add((c, NEMIK.waitsFor, a))
    return g


def test_indexed_answers_equal_the_graphs() -> None:
    g = _graph()
    nodes = sorted(set(g.subjects()), key=str)
    plain = (
        [successors(g, n) for n in nodes],
        [_open(g, n) for n in nodes],
        open_set(g),
    )
    with indexed():
        fast = (
            [successors(g, n) for n in nodes],
            [_open(g, n) for n in nodes],
            open_set(g),
        )
    assert fast == plain


def test_no_index_outside_a_build() -> None:
    assert index(_graph()) is None


def test_a_grown_graph_is_indexed_again() -> None:
    g = _graph()
    d = waypoint_uri("r", "W4")
    with indexed():
        first = index(g)
        g.add((d, OSLC_CM.state, NEMIK.Ready))
        second = index(g)
        assert second is not first
        assert second is not None
        assert second.open(d)
