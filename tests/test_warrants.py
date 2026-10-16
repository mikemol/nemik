# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W598: a card's warrants, as mtools:W1384 writes them, join the graph and meet W599."""

import copy
import json
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import PROV

from nemik.adapter import OPERATOR, queue_graph, waypoint_uri
from nemik.check import shapes
from nemik.shaclinc import findings

RECORD = URIRef("file:///t/s.jsonl#a74e004d-6a0c-4f99-897b-cc174b1ee8a4")
# the shape of `mikemol-paths-forward --warrant` output (mtools a9d4080), one human record
WARRANT: dict[str, object] = {
    "@context": {
        "prov": "http://www.w3.org/ns/prov#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "mtools": "urn:mtools:warrant#",
    },
    "@id": "urn:nemik:nemik/W1",
    "prov:wasDerivedFrom": {
        "@id": str(RECORD),
        "@type": "prov:Entity",
        "prov:generatedAtTime": {
            "@value": "2026-10-15T15:39:55.356Z",
            "@type": "xsd:dateTime",
        },
        "prov:wasAttributedTo": {"@id": "urn:nemik:operator", "@type": "prov:Agent"},
        "prov:wasGeneratedBy": {
            "@id": "urn:nemik:utterance/a74e004d",
            "@type": "prov:Activity",
        },
        "mtools:line": 6,
        "mtools:reader": "mikemol-transcriptstruct t.jsonl --verify a74e004d --claim operator",
    },
}


def _graph(tmp_path: Path, warrants: list[object]) -> Graph:
    """Read a one-card queue carrying the given warrants.

    Args:
        tmp_path: A scratch directory.
        warrants: The card's `warrants` list.

    Returns:
        The queue's graph.

    """
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "ready",
        "next_bounded_step": "x",
        "warrants": warrants,
    }
    residue: list[str] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/nemik",
        "counter": 1,
        "residue": residue,
        "waypoints": [card],
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(state))
    return queue_graph("nemik", path)


def _messages(graph: Graph) -> list[str]:
    """Run the shapes over a graph.

    Args:
        graph: The data graph.

    Returns:
        The result messages.

    """
    return [message for _, _, message in findings("w598", graph, shapes())]


def test_a_real_warrant_joins_the_graph_attributed_to_the_operator(
    tmp_path: Path,
) -> None:
    """The card is derived from the operator's record, and the record conforms."""
    graph = _graph(tmp_path, [WARRANT])
    assert (waypoint_uri("nemik", "W1"), PROV.wasDerivedFrom, RECORD) in graph
    assert (RECORD, PROV.wasAttributedTo, OPERATOR) in graph
    assert not [m for m in _messages(graph) if "warrant" in m]


def test_a_record_missing_its_time_is_named_by_the_contract(tmp_path: Path) -> None:
    """Dropping prov:generatedAtTime from mtools' output draws the W599 message."""
    broken = copy.deepcopy(WARRANT)
    record = broken["prov:wasDerivedFrom"]
    assert isinstance(record, dict)
    del record["prov:generatedAtTime"]
    assert any(
        "prov:generatedAtTime" in m for m in _messages(_graph(tmp_path, [broken]))
    )


def test_an_unparseable_entry_marks_the_card_and_warns(tmp_path: Path) -> None:
    """An entry that is not JSON-LD is not guessed at."""
    graph = _graph(tmp_path, [{"@context": {"@vocab": 3}, "@id": 5}])
    assert any("not valid JSON-LD" in m for m in _messages(graph))
