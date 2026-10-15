# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W551: the change-lifecycle scheme names five steps, each defined and witnessed."""

from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, SKOS

NEMIK = "https://github.com/mikemol/nemik/ns#"
DATA = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data" / "nemik.ttl"
STEPS = ("landed", "installed", "enabled", "active", "applied")


def _graph() -> Graph:
    graph = Graph()
    graph.parse(DATA)
    return graph


def test_the_scheme_has_exactly_the_five_steps() -> None:
    """Five concepts in the scheme, labelled with the five words."""
    graph = _graph()
    scheme = graph.resource(f"{NEMIK}ChangeLifecycle")
    members = [
        str(graph.value(concept.identifier, SKOS.prefLabel))
        for concept in scheme.subjects(SKOS.inScheme)
    ]
    assert sorted(members) == sorted(STEPS)


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
