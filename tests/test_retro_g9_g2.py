# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W651: a retro's enforcement layer is a known one, and its delta is computed."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

BAD_LAYER = "must be one of memory"
BELOW_HOOK = "below the hook layer"
NO_DELTA = "non-empty computed delta"


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
    return [m for _, _, m in findings(f"retro9-{key}", g, shapes())]


def _says(phrase: str, messages: list[str]) -> bool:
    """Say whether any message contains the phrase.

    Args:
        phrase: The text to look for.
        messages: The shapes' messages.

    Returns:
        True when one does.

    """
    return any(phrase in m for m in messages)


def test_an_unknown_enforcement_layer_is_refused() -> None:
    """Only the five named layers pass."""
    assert _says(BAD_LAYER, _retro("a", enforcementLayer="vibes", delta="d"))
    assert not _says(BAD_LAYER, _retro("b", enforcementLayer="hook", delta="d"))


def test_a_recurring_class_below_hook_is_refused_unless_one_off() -> None:
    """Memory, instructions and trigger are reminders; a hook or gate is enforcement."""
    for key, layer in (("c", "memory"), ("d", "instructions"), ("e", "trigger")):
        got = _retro(key, enforcementLayer=layer, recurring="true", delta="d")
        assert _says(BELOW_HOOK, got), layer
    for key, layer in (("f", "hook"), ("g", "gate")):
        got = _retro(key, enforcementLayer=layer, recurring="true", delta="d")
        assert not _says(BELOW_HOOK, got), layer
    one_off = _retro(
        "h", enforcementLayer="memory", recurring="true", oneOff="true", delta="d"
    )
    assert not _says(BELOW_HOOK, one_off)
    first = _retro("i", enforcementLayer="memory", delta="d")
    assert not _says(BELOW_HOOK, first)


def test_a_retro_with_no_delta_is_refused() -> None:
    """Absent or empty is not a computed delta; a recorded one is."""
    assert _says(NO_DELTA, _retro("j"))
    assert _says(NO_DELTA, _retro("k", delta=""))
    assert not _says(NO_DELTA, _retro("l", delta="predicted two files, changed five"))
