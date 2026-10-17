# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W177: a repo keeps exactly one working card unless every open item is blocked.

nemik:W529: the rule is a SPARQL constraint in shapes.ttl over the workstream's cards.
"""

from rdflib import Graph
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings


def _repo(g: Graph, repo: str, *statuses: str) -> Node:
    """Add a repo's cards in the given statuses.

    Args:
        g: The graph to add to.
        repo: The repo's name.
        *statuses: One status per card.

    Returns:
        The repo's workstream node.

    """
    ws = workstream_uri(repo)
    for i, st in enumerate(statuses, 1):
        n = waypoint_uri(repo, f"W{i}")
        g.add((n, OSLC_CM.state, STATE[st]))
        g.add((n, NEMIK.workstream, ws))
    return ws


def _said(g: Graph, ws: Node) -> list[str]:
    """Collect what the active-card shape says about a workstream.

    Args:
        g: The graph, annotated.
        ws: The workstream node.

    Returns:
        The messages naming that workstream.

    """
    annotate(g)
    key = f"active-card-{id(g)}"
    return [m for focus, _, m in findings(key, g, shapes()) if focus == ws]


def test_ready_items_and_no_working_card_is_flagged() -> None:
    """Two ready cards and nothing working: one finding, asking for a working card."""
    g = Graph()
    ws = _repo(g, "a", "ready", "ready", "blocked")
    assert [m.startswith("no working card") for m in _said(g, ws)] == [True]


def test_both_findings_are_warnings_not_violations() -> None:
    """The severity sits on the shape: a constraint-level one is ignored and reads as Violation."""
    g = Graph()
    _repo(g, "a", "ready")
    _repo(g, "b", "working", "working")
    annotate(g)
    severities = {sev for _, sev, _ in findings(f"active-{id(g)}", g, shapes())}
    assert "http://www.w3.org/ns/shacl#Violation" not in severities


def test_exactly_one_working_card_is_clean() -> None:
    """One working card beside ready ones says nothing."""
    g = Graph()
    ws = _repo(g, "a", "working", "ready", "blocked")
    assert _said(g, ws) == []


def test_several_working_cards_are_flagged() -> None:
    """Three working cards: one finding, asking to keep one."""
    g = Graph()
    ws = _repo(g, "a", "working", "working", "working")
    assert [m.startswith("more than one") for m in _said(g, ws)] == [True]


def test_all_blocked_or_done_needs_no_card() -> None:
    """Nothing ready, nothing working: no card is owed."""
    g = Graph()
    ws = _repo(g, "a", "blocked", "blocked", "done")
    assert _said(g, ws) == []
