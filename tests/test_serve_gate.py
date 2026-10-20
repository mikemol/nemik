# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W767: the view's document stages a card that a commit stack names as gating."""

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, waypoint_uri
from nemik.serve import stage_of


def test_a_card_marked_in_the_gate_is_staged_gating_and_another_has_no_stage() -> None:
    """W1 carries the in-gate mark: stage 'gating'; W2 does not: no stage."""
    g = Graph()
    g.add((waypoint_uri("a", "W1"), NEMIK.inGate, Literal("gate")))
    assert stage_of(g, waypoint_uri("a", "W1")) == "gating"
    assert not stage_of(g, waypoint_uri("a", "W2"))
