# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W530: the symbol, tags and issue time also appear as the standard Dublin Core terms."""

import json
from pathlib import Path

from rdflib import Graph, Literal
from rdflib.namespace import DCTERMS, XSD

from nemik.adapter import NEMIK, OSLC_CM, queue_graph, waypoint_uri


def test_a_completed_card_carries_its_close_date(tmp_path: Path) -> None:
    """The writer's basic-form completed stamp becomes oslc_cm:closeDate as an xsd:dateTime."""
    node = waypoint_uri("nemik", "W1")
    done = _graph(tmp_path, "2026-10-01T00:00:00Z", "20261004T205827Z")
    assert (
        node,
        OSLC_CM.closeDate,
        Literal("2026-10-04T20:58:27+00:00", datatype=XSD.dateTime),
    ) in done
    open_card = _graph(tmp_path, "2026-10-01T00:00:00Z")
    assert not list(open_card.objects(node, OSLC_CM.closeDate))


def _graph(tmp_path: Path, issued: str, completed: str = "") -> Graph:
    """Read a one-card queue.

    Args:
        tmp_path: A scratch directory.
        issued: The card's issued_at text.
        completed: The card's completed stamp, the writer's basic form; none when empty.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "done" if completed else "ready",
        "issued_at": issued,
        "touches": ["rank", "weights"],
        "next_bounded_step": "x",
    }
    if completed:
        card["completed"] = completed
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
