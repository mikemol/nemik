# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W551: the change-lifecycle scheme names five steps, each defined and witnessed."""

from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, SKOS

NEMIK = "https://github.com/mikemol/nemik/ns#"
DATA = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data" / "nemik.ttl"
STEPS = ("landed", "installed", "held", "enabled", "active", "applied")


def _graph() -> Graph:
    graph = Graph()
    graph.parse(DATA)
    return graph


def test_the_scheme_has_exactly_the_six_steps() -> None:
    """Six concepts in the scheme, labelled with the six words."""
    graph = _graph()
    scheme = graph.resource(f"{NEMIK}ChangeLifecycle")
    members = [
        str(graph.value(concept.identifier, SKOS.prefLabel))
        for concept in scheme.subjects(SKOS.inScheme)
    ]
    assert sorted(members) == sorted(STEPS)


def test_every_step_is_mapped_to_oslc_cm_or_marked_an_extension() -> None:
    """nemik:W552: a step either closely matches an OSLC CM term or says it is a nemik extension."""
    graph = _graph()
    extension = graph.resource(f"{NEMIK}extension").identifier
    cm = "http://open-services.net/ns/cm#"
    expected = {
        "landed": cm + "Fixed",
        "applied": cm + "Verified",
    }
    for step in STEPS:
        concept = graph.resource(f"{NEMIK}{step.capitalize()}").identifier
        matches = {str(m) for m in graph.objects(concept, SKOS.closeMatch)}
        marked = graph.value(concept, extension) is not None
        assert bool(matches) != marked, step  # exactly one of the two
        if step in expected:
            assert matches == {expected[step]}, step


def test_every_step_has_a_definition_and_a_witness() -> None:
    """A step without a definition or without the evidence that witnesses it is refused."""
    graph = _graph()
    witnessed = graph.resource(f"{NEMIK}witnessedBy").identifier
    for concept in graph.subjects(RDF.type, SKOS.Concept):
        if (concept, SKOS.inScheme, None) not in graph:
            continue
        label = str(graph.value(concept, SKOS.prefLabel))
        if label not in STEPS:
            continue
        assert graph.value(concept, SKOS.definition), label
        assert graph.value(concept, witnessed), label
