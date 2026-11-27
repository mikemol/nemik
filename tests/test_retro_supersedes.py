# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2529: a thin retro is retired by a retro that supersedes it and carries a sustain."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import NEMIK
from nemik.check import shapes
from nemik.retroingest import triples
from nemik.shaclinc import findings

THIN = "thin: no sustain"
KEEP = "Keep: the card map"


def _node(ident: str) -> URIRef:
    """Name a retro node as the adapter does: under its repo.

    Returns:
        The node, `urn:test:<repo>/retro/<id>`.

    """
    return URIRef(f"urn:test:{ident.partition(':')[0]}/retro/{ident}")


def _thin_ids(key: str, retros: dict[str, dict[str, str]]) -> list[str]:
    """Judge a set of retros and name those the sustain shape calls thin.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        retros: Retro id to its fields (sustain, supersedes).

    Returns:
        The sorted ids whose focus carries the thin message.

    """
    g = Graph()
    for ident, fields in retros.items():
        node = _node(ident)
        g.add((node, RDF.type, NEMIK.Retro))
        for name, value in fields.items():
            if name == "supersedes":
                # as the ingest emits it (nemik:W2552): an edge to the retro's node, resolved
                # under the superseder's own repo
                repo = ident.partition(":")[0]
                g.add(
                    (node, NEMIK.supersedes, URIRef(f"urn:test:{repo}/retro/{value}"))
                )
            else:
                g.add((node, NEMIK[name], Literal(value)))
    rows = findings(f"supersedes-{key}", g, shapes())
    return sorted(str(f).rsplit("/retro/", 1)[1] for f, _, m in rows if THIN in m)


def test_the_ingest_reads_the_supersedes_key_as_an_edge() -> None:
    """The writer's key reaches the graph as an edge to the superseded retro's node (W2552)."""
    got = triples({"id": "a:R2", "supersedes": "a:R1"})
    assert ("retro/a:R2", "supersedes", "retro/a:R1", True) in got
    assert not [t for t in got if t[1] == "supersedes" and not t[3]]


def test_a_thin_retro_with_no_superseder_stays_thin() -> None:
    """MUTANT: clearing every retro that is merely named would hide a real thin one."""
    assert _thin_ids("alone", {"a:R1": {}}) == ["a:R1"]


def test_a_retro_a_sustained_retro_supersedes_is_not_thin() -> None:
    """R2 names R1 and carries a sustain, so R1 is retired; R2 is not thin."""
    retros = {"a:R1": {}, "a:R2": {"supersedes": "a:R1", "sustain": KEEP}}
    assert _thin_ids("clears", retros) == []


def test_a_thin_superseder_is_thin_in_its_own_right() -> None:
    """W2552: R1 is history once R2 names it; R2 is the live row, judged, and thin."""
    retros = {"a:R1": {}, "a:R2": {"supersedes": "a:R1"}}
    assert _thin_ids("thin-superseder", retros) == ["a:R2"]


def test_a_chain_is_judged_at_its_live_row_only() -> None:
    """W2552: R3 supersedes R2 which supersedes R1; R1 and R2 are history, R3 is sustained."""
    retros = {
        "a:R1": {},
        "a:R2": {"supersedes": "a:R1"},
        "a:R3": {"supersedes": "a:R2", "sustain": KEEP},
    }
    assert _thin_ids("chain", retros) == []


def test_only_the_full_id_matches() -> None:
    """A short id, or another repo's R1, does not retire a:R1."""
    retros = {
        "a:R1": {},
        "b:R2": {"supersedes": "R1", "sustain": KEEP},
        "b:R3": {"supersedes": "b:R1", "sustain": KEEP},
    }
    assert _thin_ids("full-id", retros) == ["a:R1"]


def test_a_retro_does_not_supersede_itself() -> None:
    """A retro naming its own id does not clear itself."""
    retros = {"a:R1": {"supersedes": "a:R1"}}
    assert _thin_ids("self", retros) == ["a:R1"]
