# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W624: a repo's generated files leave the overlap test and ride the last entry."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.stackable import generated_files, report


def _card(symbol: str, *files: str) -> dict[str, object]:
    """Build a ready card with a manifest.

    Args:
        symbol: The card's symbol.
        *files: The files it plans to edit.

    Returns:
        The card.

    """
    return {
        "symbol": symbol,
        "title": "t",
        "status": "ready",
        "manifest": list(files),
    }


def _queue(tmp_path: Path) -> Graph:
    """Read a queue of three cards that all regenerate closures.bzl.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards = [
        _card("W1", "x.json", "closures.bzl"),
        _card("W2", "y.json", "closures.bzl"),
        _card("W3", "closures.bzl"),
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/r",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "r.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("r", path)


def test_the_listing_is_read_and_a_missing_or_bad_one_means_none() -> None:
    """Exact paths come back; empty, malformed and wrong-shaped text give none."""
    entry = '{"path": "closures.bzl", "generator": "g"}'
    text = '{"version": 1, "generated": [' + entry + "]}"
    assert generated_files(text) == frozenset({"closures.bzl"})
    assert generated_files("") == frozenset()
    assert generated_files("{not json") == frozenset()
    assert generated_files('{"generated": 3}') == frozenset()


def test_unlisted_the_shared_file_makes_the_cards_overlap(tmp_path: Path) -> None:
    """Declared but unlisted, closures.bzl is a plain conflict: only W1 stacks."""
    ranked: list[dict[str, object]] = [{"symbol": s} for s in ("W1", "W2", "W3")]
    lines = report(_queue(tmp_path), "r", ranked, [])
    assert lines[-1].startswith("1 stackable of 3")


def test_listed_all_three_stack_and_the_last_entry_carries_it(tmp_path: Path) -> None:
    """Listed as generated, closures.bzl stops conflicting and is named as the last entry's."""
    ranked: list[dict[str, object]] = [{"symbol": s} for s in ("W1", "W2", "W3")]
    lines = report(_queue(tmp_path), "r", ranked, [], frozenset({"closures.bzl"}))
    assert lines[-1].startswith("3 stackable of 3")
    assert "last entry carries: closures.bzl" in lines
