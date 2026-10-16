# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W599: the PROV-O warrant contract accepts a complete record and names what lacks."""

import json

import pytest
from rdflib import Graph

from nemik.check import shapes
from nemik.shaclinc import findings

CONTEXT = {
    "prov": "http://www.w3.org/ns/prov#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}
CARD = "urn:nemik:nemik/W599"
RECORD = "file:///home/u/.claude/projects/p/s.jsonl#0f3c-uuid"


def _card(record: dict[str, object]) -> Graph:
    """Build a graph with a card derived from one transcript record, as JSON-LD.

    Args:
        record: The record's JSON-LD properties, beyond its @id.

    Returns:
        The graph.

    """
    document = {
        "@context": CONTEXT,
        "@graph": [
            {"@id": CARD, "prov:wasDerivedFrom": {"@id": RECORD}},
            {"@id": RECORD, "@type": "prov:Entity", **record},
        ],
    }
    graph = Graph()
    graph.parse(data=json.dumps(document), format="json-ld")
    return graph


GOOD: dict[str, object] = {
    "prov:generatedAtTime": {"@value": "2026-10-16T14:02:11Z", "@type": "xsd:dateTime"},
    "prov:wasAttributedTo": {"@id": "urn:nemik:operator", "@type": "prov:Agent"},
    "prov:wasGeneratedBy": {
        "@id": "urn:nemik:utterance/0f3c",
        "@type": "prov:Activity",
    },
}


def _messages(graph: Graph) -> list[str]:
    """Run the shapes and return the result messages.

    Args:
        graph: The data graph.

    Returns:
        One message per result.

    """
    return [message for _, _, message in findings("w599-fixture", graph, shapes())]


def test_a_complete_prov_record_conforms() -> None:
    """Time, agent and activity all present: no result for the record."""
    assert not [m for m in _messages(_card(GOOD)) if "warrant" in m]


@pytest.mark.parametrize(
    ("drop", "needle"),
    [
        ("prov:generatedAtTime", "prov:generatedAtTime"),
        ("prov:wasAttributedTo", "prov:wasAttributedTo"),
        ("prov:wasGeneratedBy", "prov:wasGeneratedBy"),
    ],
)
def test_a_record_missing_a_part_is_named(drop: str, needle: str) -> None:
    """Each missing PROV part draws its own message."""
    record = {key: value for key, value in GOOD.items() if key != drop}
    assert any(needle in m for m in _messages(_card(record)))


def test_an_untyped_agent_or_a_non_datetime_time_is_refused() -> None:
    """The agent must be a prov:Agent and the time an xsd:dateTime, not a bare string."""
    bad = dict(GOOD)
    bad["prov:wasAttributedTo"] = {"@id": "urn:nemik:operator"}
    bad["prov:generatedAtTime"] = "yesterday"
    found = _messages(_card(bad))
    assert any("prov:wasAttributedTo" in m for m in found)
    assert any("prov:generatedAtTime" in m for m in found)
