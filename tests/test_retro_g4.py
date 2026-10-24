# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W983: review passes subtract earlier findings, and a fixpoint is not verified."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

REFOUND = "re-finds a finding of an earlier pass"
UNVERIFIED = "exhausted from inside, not verified"
NOT_EMPTY = "its last pass still returned findings"
HONEST = "exhausted-not-verified"
RETRO = URIRef("urn:test:retro/r1")


def _chain(key: str, passes: list[list[str]], label: str = "") -> list[str]:
    """Judge a retro whose passes returned the given findings, in order.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        passes: For each pass, the keys of the findings it returned.
        label: The retro's fixpoint label, or empty for none.

    Returns:
        The messages the shapes report.

    """
    g = Graph()
    g.add((RETRO, RDF.type, NEMIK.Retro))
    if label:
        g.add((RETRO, NEMIK.fixpointLabel, Literal(label)))
    for number, keys in enumerate(passes, start=1):
        node = URIRef(f"urn:test:pass/{key}/{number}")
        g.add((node, RDF.type, NEMIK.RetroPass))
        g.add((node, NEMIK.passOf, RETRO))
        g.add((node, NEMIK.passNumber, Literal(number)))
        for finding in keys:
            g.add((node, NEMIK.passFinding, Literal(finding)))
    return [m for _, _, m in findings(f"retro4-{key}", g, shapes())]


def _says(phrase: str, messages: list[str]) -> bool:
    """Say whether any message contains the phrase.

    Returns:
        True when one does.

    """
    return any(phrase in m for m in messages)


def test_a_pass_that_refinds_an_earlier_finding_is_refused() -> None:
    """Pass 2 repeats pass 1's key: said. A pass of new keys: not."""
    assert _says(REFOUND, _chain("a", [["x", "y"], ["y", "z"]]))
    assert not _says(REFOUND, _chain("b", [["x"], ["y"], ["z"]]))


def test_the_repeat_is_found_across_a_gap_of_passes() -> None:
    """Pass 3 repeats pass 1's key with pass 2 between: still said."""
    assert _says(REFOUND, _chain("c", [["x"], ["y"], ["x"]]))


def test_a_verified_fixpoint_is_refused_and_an_exhausted_one_is_not() -> None:
    """Only the exhausted-not-verified label is honest."""
    assert _says(UNVERIFIED, _chain("d", [["x"], []], label="verified"))
    assert not _says(UNVERIFIED, _chain("e", [["x"], []], label=HONEST))


def test_a_label_on_a_chain_whose_last_pass_found_something_is_refused() -> None:
    """The empty pass is what earns the label: a last pass with findings does not."""
    assert _says(NOT_EMPTY, _chain("f", [["x"], ["y"]], label=HONEST))
    assert not _says(NOT_EMPTY, _chain("g", [["x"], ["y"], []], label=HONEST))
