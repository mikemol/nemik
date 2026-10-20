# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W755: a retro handoff names its slots, and another operator needs a failed self probe."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

SLOTS = "must name its instrument"
NO_PROBE = "no self probe recorded executed-and-failed"


def _handoff(key: str, **fields: str) -> list[str]:
    """Judge one retro handoff with the given fields.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        **fields: Predicate local names and their values.

    Returns:
        The messages the shapes report for the handoff.

    """
    g = Graph()
    node = URIRef(f"urn:test:handoff/{key}")
    g.add((node, RDF.type, NEMIK.RetroHandoff))
    for name, value in fields.items():
        g.add((node, NEMIK[name], Literal(value)))
    return [m for _, _, m in findings(f"retro8-{key}", g, shapes())]


def _says(phrase: str, messages: list[str]) -> bool:
    """Say whether any message contains the phrase.

    Args:
        phrase: The text to look for.
        messages: The shapes' messages.

    Returns:
        True when one does.

    """
    return any(phrase in m for m in messages)


def test_a_handoff_missing_a_slot_is_named() -> None:
    """No channel: said; an operator that is neither self nor other: said."""
    assert _says(SLOTS, _handoff("a", handoffInstrument="i", handoffOperator="self"))
    got = _handoff(
        "b", handoffInstrument="i", handoffChannel="c", handoffOperator="someone"
    )
    assert _says(SLOTS, got)


def test_a_handoff_to_self_needs_no_probe() -> None:
    """Self operates it: nothing said."""
    got = _handoff(
        "c", handoffInstrument="i", handoffChannel="c", handoffOperator="self"
    )
    assert not _says(SLOTS, got)
    assert not _says(NO_PROBE, got)


def test_a_handoff_to_another_is_refused_without_a_failed_self_probe() -> None:
    """Other with no probe, or one that did not fail, is refused; a failed probe passes."""
    base = {
        "handoffInstrument": "i",
        "handoffChannel": "c",
        "handoffOperator": "other",
    }
    assert _says(NO_PROBE, _handoff("d", **base))
    assert _says(NO_PROBE, _handoff("e", **base, selfProbe="not tried"))
    assert not _says(NO_PROBE, _handoff("f", **base, selfProbe="executed-and-failed"))
