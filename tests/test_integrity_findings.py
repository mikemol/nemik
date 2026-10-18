# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W693: an enables edge into a card that does not wait on its source is named."""

from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.check import integrity_commands, integrity_findings


def _card(g: Graph, symbol: str, state: str = "blocked") -> None:
    g.add((waypoint_uri("alpha", symbol), OSLC_CM.state, STATE[state]))


def _edge(g: Graph, source: str, kind: str, target: str) -> None:
    predicate = NEMIK.waitsFor if kind == "waits" else NEMIK.enables
    g.add((waypoint_uri("alpha", source), predicate, waypoint_uri("alpha", target)))


def test_an_enabled_card_that_does_not_wait_on_its_source_is_named() -> None:
    """W1 enables W2, but W2 waits on nothing: the two edge kinds disagree."""
    g = Graph()
    for symbol in ("W1", "W2"):
        _card(g, symbol)
    _edge(g, "W1", "enables", "W2")
    got = integrity_findings(g)
    assert list(got) == ["alpha"]
    symbol, said = got["alpha"][0]
    assert symbol == "W1"
    assert "alpha:W2" in said


def test_an_enabled_card_that_waits_on_its_source_is_not() -> None:
    """W2 waits on W1, so W1's enables edge is backed by a blocked_on edge."""
    g = Graph()
    for symbol in ("W1", "W2"):
        _card(g, symbol)
    _edge(g, "W1", "enables", "W2")
    _edge(g, "W2", "waits", "W1")
    assert integrity_findings(g) == {}


def test_a_join_is_not_a_finding() -> None:
    """W3 waits on W1 and W2, so W1 enabling W3 is backed though W3 has other blockers."""
    g = Graph()
    for symbol in ("W1", "W2", "W3"):
        _card(g, symbol)
    _edge(g, "W1", "enables", "W3")
    _edge(g, "W3", "waits", "W1")
    _edge(g, "W3", "waits", "W2")
    assert integrity_findings(g) == {}


def test_a_done_card_is_not_part_of_the_graph() -> None:
    """An enabled card that is already done escapes nothing."""
    g = Graph()
    _card(g, "W1")
    _card(g, "W2", "done")
    _edge(g, "W1", "enables", "W2")
    assert integrity_findings(g) == {}


def test_the_dry_run_prints_both_fixes_and_applies_neither() -> None:
    """Drop the enables edge, or add the blocked_on; the commands name the repo's state file."""
    g = Graph()
    for symbol in ("W1", "W2"):
        _card(g, symbol)
    _edge(g, "W1", "enables", "W2")
    lines = integrity_commands(g, Path("/fleet"))["alpha"]
    assert lines[0] == "alpha:W1: enables alpha:W2, which does not wait on it"
    state = "/fleet/alpha/.claude/paths-forward.json"
    assert lines[1].endswith(f"{state} --update W1 --enables")
    assert f"{state} --update W2 --blocked-on W1 --blocked-kind agent" in lines[2]
