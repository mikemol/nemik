# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W611: nemik-stackable --drift reports files a done card touched past its manifest."""

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.stackable_cli import drift_lines


def _card(g: Graph, symbol: str, state: str, planned: list[str]) -> None:
    node = waypoint_uri("alpha", symbol)
    g.add((node, OSLC_CM.state, STATE[state]))
    for path in planned:
        g.add((node, NEMIK.plannedPath, Literal(path)))


def _touched(symbol: str) -> list[str]:
    files = {
        "W1": ["src/a.py", "tests/test_a.py", "BUILD.bazel"],
        "W2": ["src/b.py", "tests/test_b.py"],
        "W3": ["src/c.py", "tests/test_c.py"],
        "W4": ["src/d.py", "tests/test_d.py"],
    }
    return files[symbol]


def test_a_done_card_reports_the_files_beyond_its_manifest() -> None:
    """Only done cards with a manifest and some drift get a line."""
    g = Graph()
    _card(g, "W1", "done", ["src/a.py"])
    _card(g, "W2", "done", ["src/b.py", "tests/test_b.py"])
    _card(g, "W3", "ready", ["src/c.py"])
    _card(g, "W4", "done", [])
    lines = drift_lines(g, "alpha", _touched, 2)
    assert lines == ["W1: drift BUILD.bazel tests/test_a.py"]


def test_a_kind_missed_by_enough_cards_rides_along() -> None:
    """tests/ missing from two manifests is reported as a kind to add to drafts."""
    g = Graph()
    _card(g, "W1", "done", ["src/a.py"])
    _card(g, "W3", "done", ["src/c.py"])
    lines = drift_lines(g, "alpha", _touched, 2)
    assert "ride-along: tests/ missed by 2 cards" in lines
    assert not any("BUILD.bazel missed" in line for line in lines)
