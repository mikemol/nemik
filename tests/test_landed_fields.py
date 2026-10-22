# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W841: the deploys flag and landed_at stamp are read; done without a witness warns."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, queue_graph, waypoint_uri
from nemik.check import shapes
from nemik.shaclinc import findings

WITNESS = "serving_sha == card_sha"


def _queue(tmp_path: Path, cards: list[dict[str, object]]) -> Graph:
    """Read a queue of the given cards.

    Args:
        tmp_path: A scratch directory.
        cards: The queue's waypoints.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("a", path)


def _card(symbol: str, status: str, **more: object) -> dict[str, object]:
    """Build a card.

    Returns:
        The card.

    """
    return {"symbol": symbol, "title": symbol, "status": status, **more}


def _unwitnessed(g: Graph) -> set[str]:
    """Collect the symbols the done-without-witness Warning names.

    Returns:
        W1 to W4 among them.

    """
    rows = findings(f"deploy-{id(g)}", g, shapes())
    named = {
        str(focus) for focus, _, m in rows if "declares no witness that shows" in m
    }
    return {s for s in ("W1", "W2", "W3", "W4") if str(waypoint_uri("a", s)) in named}


def test_the_deploys_flag_and_landing_stamp_are_read_from_the_card(
    tmp_path: Path,
) -> None:
    """A deploys flag becomes nemik:deploys; landed_at becomes an xsd:dateTime."""
    g = _queue(
        tmp_path,
        [_card("W1", "landed", deploys=True, landed_at="20261022T101500Z")],
    )
    node = waypoint_uri("a", "W1")
    assert str(g.value(node, NEMIK.deploys)) == "true"
    assert str(g.value(node, NEMIK.landedAt)).startswith("2026-10-22T10:15:00")


def test_a_card_that_does_not_deploy_reads_neither_field(tmp_path: Path) -> None:
    """No deploys and no landed_at leave the graph without either triple."""
    g = _queue(tmp_path, [_card("W1", "done")])
    node = waypoint_uri("a", "W1")
    assert g.value(node, NEMIK.deploys) is None
    assert g.value(node, NEMIK.landedAt) is None


def test_only_a_done_deploying_card_without_a_witness_warns(tmp_path: Path) -> None:
    """W1 done+deploys+no witness is named; with a witness, not deploying, or landed, it is not."""
    g = _queue(
        tmp_path,
        [
            _card("W1", "done", deploys=True),
            _card("W2", "done", deploys=True, witness=WITNESS),
            _card("W3", "done"),
            _card("W4", "landed", deploys=True),
        ],
    )
    assert _unwitnessed(g) == {"W1"}
