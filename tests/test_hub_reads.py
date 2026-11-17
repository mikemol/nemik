# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2225: the predicates a hub-level shape reads are named from the shapes, not hard-coded."""

from __future__ import annotations

from rdflib import Graph

from nemik.check import shapes
from nemik.shaclinc import hub_reads

SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
ex:HubShape a sh:NodeShape ;
    sh:targetClass ex:Workstream ;
    sh:sparql [ sh:select \"\"\"SELECT $this WHERE { ?c <http://example.org/inRepo> $this ;
        <http://example.org/flag> ?f }\"\"\" ] ;
    sh:property [ sh:path ex:size ] .
ex:CardShape a sh:NodeShape ;
    sh:targetClass ex:Card ;
    sh:sparql [ sh:select \"\"\"SELECT $this WHERE { $this <http://example.org/other> ?o }\"\"\" ] .
"""


def test_only_hub_shapes_count() -> None:
    """A card shape's predicate is not read off a hub's neighbours; a hub shape's are."""
    graph = Graph()
    graph.parse(data=SHAPES, format="turtle")
    assert hub_reads(graph) == {"workstream", "inRepo", "flag", "size"}


def test_the_shipped_hub_shapes_read_the_state_and_the_workstream() -> None:
    """The real shapes' hub rules read each card's state and its workstream edge."""
    reads = hub_reads(shapes())
    assert {"workstream", "state"} <= reads
    assert "type" not in reads
