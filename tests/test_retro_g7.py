# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W754: a retro finding is an action: a complete card, or a certify change."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

NO_ACTION = "must reference a card"
INCOMPLETE = "needs an owner"


def _finding(key: str, **fields: str) -> list[str]:
    """Judge one retro finding with the given fields.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        **fields: Predicate local names and their values.

    Returns:
        The messages the shapes report for the finding.

    """
    g = Graph()
    node = URIRef(f"urn:test:finding/{key}")
    g.add((node, RDF.type, NEMIK.RetroFinding))
    for name, value in fields.items():
        g.add((node, NEMIK[name], Literal(value)))
    return [m for _, _, m in findings(f"retro7-{key}", g, shapes())]


def _says(phrase: str, messages: list[str]) -> bool:
    """Say whether any message contains the phrase.

    Args:
        phrase: The text to look for.
        messages: The shapes' messages.

    Returns:
        True when one does.

    """
    return any(phrase in m for m in messages)


def test_a_finding_with_neither_card_nor_certify_change_is_an_observation() -> None:
    """Only prose, no card and no verdict change: said."""
    assert _says(NO_ACTION, _finding("a"))


def test_a_certify_change_is_an_action_by_itself() -> None:
    """A verdict change needs no card."""
    got = _finding("b", certifyChange="W12 certified to uncertified")
    assert not _says(NO_ACTION, got)
    assert not _says(INCOMPLETE, got)


def test_a_card_without_owner_due_and_witness_is_incomplete() -> None:
    """The card is named, so it is an action, but it is not yet one anyone owns."""
    got = _finding("c", findingCard="nemik:W9")
    assert not _says(NO_ACTION, got)
    assert _says(INCOMPLETE, got)


def test_a_card_with_owner_due_and_witness_is_complete() -> None:
    """All three present: nothing said."""
    got = _finding(
        "d",
        findingCard="nemik:W9",
        findingOwner="nemik",
        due="20261101T000000Z",
        findingWitness="a git ref containing the commit",
    )
    assert not _says(NO_ACTION, got)
    assert not _says(INCOMPLETE, got)
