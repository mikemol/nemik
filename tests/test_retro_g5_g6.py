# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W649: a retro's root is checked for blame wording, and its sustain is not left empty."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

BLAME = "the root reads as blame"
THIN = "thin: no sustain"


def _retro(key: str, **fields: str) -> list[str]:
    """Judge one retro node with the given fields.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        **fields: The retro's trigger, root, precommit and sustain values.

    Returns:
        The messages the shapes report for the retro.

    """
    g = Graph()
    node = URIRef(f"urn:test:retro/{key}")
    g.add((node, RDF.type, NEMIK.Retro))
    for name, value in fields.items():
        g.add((node, NEMIK[name], Literal(value)))
    return [m for _, _, m in findings(f"retro5-{key}", g, shapes())]


def _says(phrase: str, messages: list[str]) -> bool:
    """Say whether any message contains the phrase.

    Args:
        phrase: The text to look for.
        messages: The shapes' messages.

    Returns:
        True when one does.

    """
    return any(phrase in m for m in messages)


def test_a_root_that_blames_a_person_or_a_lapse_is_named_with_a_rewrite_hint() -> None:
    """'Forgot', 'should have' and 'careless' are named, and the message says how to rewrite."""
    for key, root in (
        ("a", "The agent forgot to run the check"),
        ("b", "It should have been caught in review"),
        ("c", "Careless edit of the hook"),
    ):
        got = _retro(key, trigger="t", root=root, sustain="s")
        assert _says(BLAME, got), root
        assert _says("nothing reminded X of Y", got)


def test_a_root_that_names_a_condition_is_not() -> None:
    """The same facts worded as a condition pass, and a word inside another word does not match."""
    for key, root in (
        ("d", "Nothing reminded the agent to run the check"),
        ("e", "The hook reads its file while it is being replaced"),
        ("f", "Unforgotten edge cases"),
    ):
        assert not _says(BLAME, _retro(key, trigger="t", root=root, sustain="s")), root


def test_a_retro_with_no_sustain_is_thin() -> None:
    """No sustain, or an empty one, is said; a recorded one is not."""
    assert _says(THIN, _retro("g", trigger="t", root="r"))
    assert _says(THIN, _retro("h", trigger="t", root="r", sustain=""))
    kept = _retro("i", trigger="t", root="r", sustain="the snapshot re-exec")
    assert not _says(THIN, kept)
