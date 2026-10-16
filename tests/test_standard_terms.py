# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W530: the symbol, tags and issue time also appear as the standard Dublin Core terms."""

import json
from pathlib import Path

from rdflib import Graph, Literal
from rdflib.namespace import DCTERMS, XSD

from nemik.adapter import NEMIK, queue_graph, waypoint_uri


def _graph(tmp_path: Path, issued: str) -> Graph:
    """Read a one-card queue.

    Args:
        tmp_path: A scratch directory.
        issued: The card's issued_at text.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "ready",
        "issued_at": issued,
        "touches": ["rank", "weights"],
        "next_bounded_step": "x",
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/nemik",
        "counter": 1,
        "residue": residue,
        "waypoints": [card],
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("nemik", path)


def test_the_standard_terms_sit_beside_the_nemik_ones(tmp_path: Path) -> None:
    """The identifier and subject repeat symbol and touches; created is an xsd:dateTime."""
    graph = _graph(tmp_path, "2026-10-16T14:02:11Z")
    node = waypoint_uri("nemik", "W1")
    assert (node, NEMIK.symbol, Literal("W1")) in graph
    assert (node, DCTERMS.identifier, Literal("W1")) in graph
    assert {str(o) for o in graph.objects(node, DCTERMS.subject)} == {"rank", "weights"}
    assert (
        node,
        DCTERMS.created,
        Literal("2026-10-16T14:02:11Z", datatype=XSD.dateTime),
    ) in graph


def test_a_stamp_that_is_not_an_instant_stays_as_written(tmp_path: Path) -> None:
    """No offset, or not a date at all: the text is kept, never mistyped."""
    for text in ("2026-10-16T14:02:11", "soon"):
        graph = _graph(tmp_path, text)
        node = waypoint_uri("nemik", "W1")
        assert (node, DCTERMS.created, Literal(text)) in graph
