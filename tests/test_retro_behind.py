# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W988: a repo behind a ratchet's paydown rate needs an open card on the ratchet's file."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK, OSLC_CM
from nemik.check import shapes
from nemik.shaclinc import findings

SAID = "no open card touches that ratchet's file"
REPO = URIRef("urn:test:ws/nemik")


def _judged(key: str, touches: str, state: URIRef = NEMIK.Ready) -> list[str]:
    """Judge a repo behind on ruff-baseline.json with one card touching the given tag.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        touches: The card's touches tag, or empty for a card that touches nothing.
        state: The card's state.

    Returns:
        The messages the shapes report.

    """
    g = Graph()
    g.add((REPO, RDF.type, NEMIK.Workstream))
    g.add((REPO, NEMIK.behindOn, Literal("ruff-baseline.json")))
    card = URIRef(f"urn:test:card/{key}")
    g.add((card, NEMIK.workstream, REPO))
    g.add((card, OSLC_CM.state, state))
    if touches:
        g.add((card, NEMIK.touches, Literal(touches)))
    return [m for _, _, m in findings(f"behind-{key}", g, shapes())]


def _says(messages: list[str]) -> bool:
    """Say whether any message is the shape's.

    Returns:
        True when one is.

    """
    return any(SAID in m for m in messages)


def test_a_behind_repo_with_no_paydown_card_is_named() -> None:
    """A card on another file, or none, leaves the repo without a paydown card."""
    assert _says(_judged("a", "file:src/nemik/serve.py!w"))
    assert _says(_judged("b", ""))


def test_a_card_touching_the_ratchet_file_pays_it_down() -> None:
    """With and without the write suffix, an open card on the file satisfies the shape."""
    assert not _says(_judged("c", "file:ruff-baseline.json!w"))
    assert not _says(_judged("d", "file:ruff-baseline.json"))


def test_a_done_card_on_the_file_does_not_count() -> None:
    """The card has to be open."""
    assert _says(_judged("e", "file:ruff-baseline.json!w", NEMIK.Done))
