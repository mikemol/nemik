# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1011: a card blocked on an operator act needs an executed probe in its evidence."""

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import XSD

from nemik.adapter import NEMIK, OSLC_CM, has_probe
from nemik.check import shapes
from nemik.shaclinc import findings

SAID = "no executed probe in its evidence"


def _judged(key: str, blocked_on: str, *, probe: bool) -> list[str]:
    """Judge one blocked card.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        blocked_on: The card's blocked_on text.
        probe: Whether the card records an executed probe.

    Returns:
        The messages the shapes report.

    """
    g = Graph()
    card = URIRef(f"urn:test:card/{key}")
    g.add((card, RDF.type, OSLC_CM.ChangeRequest))
    g.add((card, OSLC_CM.state, NEMIK.Blocked))
    g.add((card, NEMIK.blockedOn, Literal(blocked_on)))
    if probe:
        g.add((card, NEMIK.probeRecorded, Literal("true", datatype=XSD.boolean)))
    return [m for _, _, m in findings(f"probe-{key}", g, shapes())]


def _says(messages: list[str]) -> bool:
    """Say whether any message is the shape's.

    Returns:
        True when one is.

    """
    return any(SAID in m for m in messages)


def test_an_operator_act_with_no_probe_is_named() -> None:
    """An act ask, in either case, with no probe recorded."""
    assert _says(_judged("a", "operator: act run the repin", probe=False))
    assert _says(_judged("b", "Operator: ACT sudo systemctl restart x", probe=False))


def test_a_probe_or_a_decision_is_not_named() -> None:
    """A recorded probe clears an act; a decide ask is a choice and needs none."""
    assert not _says(_judged("c", "operator: act run the repin", probe=True))
    assert not _says(_judged("d", "operator: decide which of two", probe=False))


def test_the_evidence_forms_that_count_as_a_probe() -> None:
    """Ran, executed, an exit status and a prompt line count; plain prose does not."""
    yes = ["I ran it", "executed the step", "it exited 2", "exit code 0", "$ ls\nout"]
    assert all(has_probe(text) for text in yes)
    assert not has_probe("the operator should run the repin")
