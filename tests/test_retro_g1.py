# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W757: a retro records the hash of its frozen timeline."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

NOT_FROZEN = "no frozen timeline"


def _retro(key: str, **fields: str) -> list[str]:
    """Judge one retro node with the given fields.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        **fields: Predicate local names and their values.

    Returns:
        The messages the shapes report for the retro.

    """
    g = Graph()
    node = URIRef(f"urn:test:retro/{key}")
    g.add((node, RDF.type, NEMIK.Retro))
    for name, value in fields.items():
        g.add((node, NEMIK[name], Literal(value)))
    return [m for _, _, m in findings(f"retro1-{key}", g, shapes())]


def test_a_retro_without_a_timeline_hash_is_said_to_be_unfrozen() -> None:
    """Absent or empty is said; a recorded hash is not."""
    assert any(NOT_FROZEN in m for m in _retro("a"))
    assert any(NOT_FROZEN in m for m in _retro("b", frozenTimeline=""))
    frozen = _retro("c", frozenTimeline="sha256:0f3a")
    assert not any(NOT_FROZEN in m for m in frozen)
