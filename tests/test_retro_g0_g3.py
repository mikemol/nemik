# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W648: a retro without a precommit is narrative only and names a root unlike its trigger."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

NARRATIVE = "narrative only"
NAMES = "must name its trigger and its root"
SAME = "the root equals the trigger"


def _retro(key: str, **fields: str) -> list[str]:
    """Judge one retro node with the given fields.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        **fields: The retro's trigger, root, precommit and contributing values.

    Returns:
        The messages the shapes report for the retro.

    """
    g = Graph()
    node = URIRef(f"urn:test:retro/{key}")
    g.add((node, RDF.type, NEMIK.Retro))
    for name, value in fields.items():
        g.add((node, NEMIK[name], Literal(value)))
    return [m for _, _, m in findings(f"retro-{key}", g, shapes())]


def _says(phrase: str, messages: list[str]) -> bool:
    """Say whether any message contains the phrase.

    Args:
        phrase: The text to look for.
        messages: The shapes' messages.

    Returns:
        True when one does.

    """
    return any(phrase in m for m in messages)


def test_a_retro_with_no_precommit_is_narrative_only() -> None:
    """No precommit: the Info row says so; one with a precommit does not."""
    assert _says(NARRATIVE, _retro("a", trigger="t", root="r"))
    assert not _says(NARRATIVE, _retro("b", trigger="t", root="r", precommit="p"))


def test_an_empty_precommit_counts_as_none() -> None:
    """An empty string records nothing."""
    assert _says(NARRATIVE, _retro("c", trigger="t", root="r", precommit=""))


def test_a_retro_must_name_a_trigger_and_a_root() -> None:
    """Missing either is a violation; naming both is not."""
    assert _says(NAMES, _retro("d", root="r", precommit="p"))
    assert _says(NAMES, _retro("e", trigger="t", precommit="p"))
    assert not _says(NAMES, _retro("f", trigger="t", root="r", precommit="p"))


def test_the_root_must_differ_from_the_trigger() -> None:
    """A root equal to the trigger is named; a different root is not."""
    assert _says(SAME, _retro("g", trigger="x", root="x", precommit="p"))
    assert not _says(SAME, _retro("h", trigger="x", root="y", precommit="p"))
