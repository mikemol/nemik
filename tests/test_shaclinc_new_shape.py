# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W637: a shape that starts reading a predicate makes that predicate count at once."""

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SH

from nemik.adapter import BASE, NEMIK
from nemik.shaclinc import findings, watched_predicates

POSITION = "https://github.com/mikemol/nemik/ns#queuePosition"
READS_POSITION = f"""
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/> .
ex:Late a sh:NodeShape ;
  sh:targetSubjectsOf <{POSITION}> ;
  sh:sparql [
    a sh:SPARQLConstraint ;
    sh:message "queued past the first place" ;
    sh:select \"\"\"SELECT $this WHERE {{ $this <{POSITION}> ?p . FILTER(?p > 1) }}\"\"\" ] .
"""


def test_a_shape_that_reads_queue_position_watches_it() -> None:
    """The predicate is taken from the shapes' own query text, never from a list."""
    shapes = Graph().parse(data=READS_POSITION, format="turtle")
    texts = [str(t) for t in shapes.objects(None, SH.select)]
    assert "queuePosition" in watched_predicates(shapes, texts)


def test_a_change_to_a_predicate_a_shape_reads_is_judged_again() -> None:
    """Position 1 passes and position 2 fails: the second run must not serve the first verdict."""
    shapes = Graph().parse(data=READS_POSITION, format="turtle")
    card = URIRef(f"{BASE}new-shape-test/W1")
    first = Graph()
    first.add((card, NEMIK.queuePosition, Literal(1)))
    second = Graph()
    second.add((card, NEMIK.queuePosition, Literal(2)))
    assert findings("new-shape-key", first, shapes) == []
    later = findings("new-shape-key", second, shapes)
    assert [(f, m) for f, _, m in later] == [(card, "queued past the first place")]
