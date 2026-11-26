# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2545: a handoff that fails the probe shape is retired by a retro that supersedes it."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.shaclinc import findings

PROBE = "another operator with no self probe"
FAILED = "executed-and-failed"
HANDOFF = "handoff"


def _retro(ident: str) -> URIRef:
    """Name a retro node as the adapter does: under its repo.

    Returns:
        The node, `urn:test:<repo>/retro/<id>`.

    """
    return URIRef(f"urn:test:{ident.partition(':')[0]}/retro/{ident}")


def _refused_ids(key: str, retros: dict[str, dict[str, str]]) -> list[str]:
    """Judge a set of retros and name those whose handoff the probe shape refuses.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        retros: Retro id to its fields; `supersedes` and the handoff fields (operator, self_probe).

    Returns:
        The sorted retro ids whose handoff node carries the probe message.

    """
    g = Graph()
    for ident, fields in retros.items():
        node = _retro(ident)
        hand = URIRef(f"{node}/{HANDOFF}")
        g.add((node, RDF.type, NEMIK.Retro))
        g.add((node, NEMIK[HANDOFF], hand))
        g.add((hand, RDF.type, NEMIK.RetroHandoff))
        if "supersedes" in fields:
            g.add((node, NEMIK.supersedes, Literal(fields["supersedes"])))
        g.add((hand, NEMIK.handoffOperator, Literal(fields["operator"])))
        if "self_probe" in fields:
            g.add((hand, NEMIK.selfProbe, Literal(fields["self_probe"])))
    rows = findings(f"handoff-supersedes-{key}", g, shapes())
    return sorted(
        str(f).rsplit("/retro/", 1)[1].removesuffix(f"/{HANDOFF}")
        for f, _, m in rows
        if PROBE in m
    )


def test_an_other_handoff_with_no_probe_and_no_superseder_stays_refused() -> None:
    """MUTANT: retiring every handoff would hide a real unprobed one."""
    assert _refused_ids("alone", {"a:R1": {"operator": "other"}}) == ["a:R1"]


def test_a_superseder_with_a_self_handoff_retires_it() -> None:
    """R2 names R1 and its handoff is self, so R1 is retired; R2 passes."""
    retros = {
        "a:R1": {"operator": "other"},
        "a:R2": {"operator": "self", "supersedes": "a:R1"},
    }
    assert _refused_ids("self", retros) == []


def test_a_superseder_with_a_recorded_probe_retires_it() -> None:
    """R2 hands to another operator with the probe recorded executed-and-failed."""
    retros = {
        "a:R1": {"operator": "other"},
        "a:R2": {"operator": "other", "self_probe": FAILED, "supersedes": "a:R1"},
    }
    assert _refused_ids("probe", retros) == []


def test_a_superseder_whose_handoff_still_fails_clears_nothing() -> None:
    """R2 names R1 but hands to another operator with no probe: both stay refused."""
    retros = {
        "a:R1": {"operator": "other"},
        "a:R2": {"operator": "other", "supersedes": "a:R1"},
    }
    assert _refused_ids("still-failing", retros) == ["a:R1", "a:R2"]


def test_only_the_full_id_of_the_same_repo_retires_it() -> None:
    """A short id, or another repo's R1, does not retire a:R1."""
    retros = {
        "a:R1": {"operator": "other"},
        "b:R2": {"operator": "self", "supersedes": "R1"},
        "b:R3": {"operator": "self", "supersedes": "b:R1"},
    }
    assert _refused_ids("full-id", retros) == ["a:R1"]


def test_a_retro_does_not_supersede_itself() -> None:
    """A retro naming its own id does not clear its own handoff."""
    retros = {"a:R1": {"operator": "other", "supersedes": "a:R1"}}
    assert _refused_ids("self-named", retros) == ["a:R1"]
