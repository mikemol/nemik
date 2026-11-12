# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W551: the change-lifecycle scheme names five steps, each defined and witnessed."""

from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS

if TYPE_CHECKING:
    from rdflib.term import Node

NEMIK = "https://github.com/mikemol/nemik/ns#"
DATA = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data" / "nemik.ttl"
STEPS = ("landed", "installed", "held", "enabled", "active", "applied")


def _graph() -> Graph:
    graph = Graph()
    graph.parse(DATA)
    return graph


def _first(graph: Graph, subject: Node, predicate: URIRef) -> Node | None:
    """Read the first object of a (subject, predicate) pair.

    Returns:
        The object, or None when the graph has none.

    """
    return next(iter(graph.objects(subject, predicate)), None)


def test_the_scheme_has_exactly_the_six_steps() -> None:
    """Six concepts in the scheme, labelled with the six words."""
    graph = _graph()
    scheme = URIRef(f"{NEMIK}ChangeLifecycle")
    members = [
        str(_first(graph, concept, SKOS.prefLabel))
        for concept in graph.subjects(SKOS.inScheme, scheme)
    ]
    assert sorted(members) == sorted(STEPS)


def test_every_step_is_mapped_to_oslc_cm_or_marked_an_extension() -> None:
    """nemik:W552: a step either closely matches an OSLC CM term or says it is a nemik extension."""
    graph = _graph()
    extension = URIRef(f"{NEMIK}extension")
    cm = "http://open-services.net/ns/cm#"
    expected = {
        "landed": cm + "Fixed",
        "applied": cm + "Verified",
    }
    for step in STEPS:
        concept = URIRef(f"{NEMIK}{step.capitalize()}")
        matches = {str(m) for m in graph.objects(concept, SKOS.closeMatch)}
        marked = _first(graph, concept, extension) is not None
        assert bool(matches) != marked, step  # exactly one of the two
        if step in expected:
            assert matches == {expected[step]}, step


def test_every_step_has_a_definition_and_a_witness() -> None:
    """A step without a definition or without the evidence that witnesses it is refused."""
    graph = _graph()
    witnessed = URIRef(f"{NEMIK}witnessedBy")
    for concept in graph.subjects(RDF.type, SKOS.Concept):
        if (concept, SKOS.inScheme, None) not in graph:
            continue
        label = str(_first(graph, concept, SKOS.prefLabel))
        if label not in STEPS:
            continue
        assert _first(graph, concept, SKOS.definition), label
        assert _first(graph, concept, witnessed), label
