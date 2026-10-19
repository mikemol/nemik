# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W685: a repo's ready cards without a manifest may not pass the ratchet declared for it."""

from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import BASE, NEMIK, OSLC_CM
from nemik.blocks import lowered_ratchet, over_ratchet, unmanifested_by_repo
from nemik.check import manifest_findings, manifest_ratchet


def _fleet() -> Graph:
    """Build a graph: repo alpha with two ready cards, one manifested; repo beta with none.

    Returns:
        The merged graph.

    """
    g = Graph()
    for repo in ("alpha", "beta"):
        g.add((URIRef(BASE + repo), RDF.type, NEMIK.Workstream))
    for sym in ("W1", "W2"):
        node = URIRef(BASE + "alpha/" + sym)
        g.add((node, OSLC_CM.state, NEMIK.Ready))
    g.add((URIRef(BASE + "alpha/W2"), NEMIK.plannedPath, Literal("src/a.py")))
    return g


def test_counts_only_ready_cards_without_a_manifest() -> None:
    """Repo alpha has one unmanifested ready card, beta none."""
    assert unmanifested_by_repo(_fleet()) == {"alpha": 1, "beta": 0}


def test_at_the_ratchet_is_quiet_and_over_it_warns() -> None:
    """A repo at its declared count is silent; one over it is named with both numbers."""
    counts = unmanifested_by_repo(_fleet())
    assert not over_ratchet(counts, {"alpha": 1})
    assert over_ratchet(counts, {"alpha": 0}) == {"alpha": (1, 0)}
    assert "alpha" in manifest_findings(_fleet(), {"alpha": 0})
    assert not manifest_findings(_fleet(), {"alpha": 1})


def test_an_undeclared_repo_is_declared_at_zero() -> None:
    """A repo the table does not name may carry no unmanifested ready card."""
    assert over_ratchet({"gamma": 2}, {}) == {"gamma": (2, 0)}


def test_the_ratchet_only_falls() -> None:
    """The lowered table takes the smaller of today's count and the declared one."""
    assert lowered_ratchet({"a": 1, "b": 5, "c": 2}, {"a": 3, "b": 4}) == {
        "a": 1,
        "b": 4,
        "c": 2,
    }


def test_the_table_ships_in_rank_weights() -> None:
    """The packaged table names the fleet's repos with non-negative counts."""
    declared = manifest_ratchet()
    assert declared
    assert all(n >= 0 for n in declared.values())
