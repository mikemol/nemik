# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W600: the fleet ranking puts a more urgent repo's cards first."""

import json
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.rank import load_composition, main


def _queue(tmp_path: Path, repo: str, symbols: list[str]) -> Graph:
    """Read a queue of ready cards.

    Args:
        tmp_path: A scratch directory.
        repo: The repo's name.
        symbols: The ready cards' symbols.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {"symbol": s, "title": s, "status": "ready", "next_bounded_step": "x"}
        for s in symbols
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": f"/{repo}",
        "counter": 9,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / f"{repo}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(repo, path)


def test_the_packaged_composition_is_unchanged_per_repo() -> None:
    """The tier orders only the cross-repo pool, so a per-repo composition has no tier tier."""
    assert ("tier",) not in load_composition().tiers


def test_a_table_that_is_not_one_reads_as_the_default_composition() -> None:
    """nemik:W1253: an [order] that is not a table is empty, so the defaults stand."""
    comp = load_composition("order = 3\n")
    assert comp.tiers == (("weight",),)
    assert comp.weight_model == "downstream"


def test_a_scalarize_that_is_not_a_table_reads_as_empty() -> None:
    """nemik:W1253: a scalarize that is not a table is empty, where it used to raise."""
    assert load_composition("[order]\nscalarize = 3\n").scalarize == {}


def test_scalarize_numbers_read_as_floats() -> None:
    """nemik:W1253: an integer and a float under scalarize both read as floats."""
    comp = load_composition("[order.scalarize]\nweight = 2\nblocked = 1.5\n")
    assert comp.scalarize == {"weight": 2.0, "blocked": 1.5}


def test_a_boolean_under_scalarize_is_refused() -> None:
    """nemik:W1253: float(str(True)) is not a number, so a boolean no longer reads as 1.0."""
    with pytest.raises(ValueError, match="could not convert"):
        load_composition("[order.scalarize]\nweight = true\n")


def test_the_fleet_orders_by_tier_before_symbol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Substrate (later) W1 would win on its lower symbol; nemik (now) W5 wins on its tier."""
    merged = _queue(tmp_path, "substrate", ["W1"])
    merged += _queue(tmp_path, "nemik", ["W5"])
    main(["--all"], merged)
    out = capsys.readouterr().out
    assert out.index("nemik:W5") < out.index("substrate:W1")
