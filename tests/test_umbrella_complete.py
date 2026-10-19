# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W488: an umbrella whose children are all done and that states no step is named."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, queue_graph, waypoint_uri
from nemik.check import shapes
from nemik.shaclinc import findings


def _umbrella(tmp_path: Path, name: str, cards: list[dict[str, object]]) -> Graph:
    """Read a queue whose W1 is an umbrella over the other cards.

    Args:
        tmp_path: A scratch directory.
        name: The repo's name.
        cards: The queue's waypoints.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": f"/{name}",
        "counter": len(cards),
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(name, path)


def _kid(symbol: str, status: str) -> dict[str, object]:
    """Build a child card that enables W1.

    Args:
        symbol: The child's symbol.
        status: Its status.

    Returns:
        The card.

    """
    return {"symbol": symbol, "title": "kid", "status": status, "enables": ["W1"]}


def _top(**more: object) -> dict[str, object]:
    """Build the umbrella card.

    Args:
        **more: Fields that override the defaults.

    Returns:
        The card: ready, with no next step.

    """
    return {"symbol": "W1", "title": "umbrella", "status": "ready", **more}


def _flagged(g: Graph, name: str, phrase: str = "realized by construction") -> bool:
    """Say whether a shape names the repo's W1.

    Args:
        g: The queue's graph.
        name: The repo's name.
        phrase: A phrase of the message to look for.

    Returns:
        True when a finding with that phrase reports W1.

    """
    node = waypoint_uri(name, "W1")
    rows = findings(f"umbrella-{id(g)}", g, shapes())
    return any(focus == node and phrase in m for focus, _, m in rows)


def test_all_children_done_and_no_step_is_named(tmp_path: Path) -> None:
    """Two done children, no next step, no foreign wait: the umbrella is named."""
    g = _umbrella(tmp_path, "a", [_top(), _kid("W2", "done"), _kid("W3", "done")])
    assert _flagged(g, "a")


def test_an_open_child_a_next_step_or_a_working_umbrella_keeps_it(
    tmp_path: Path,
) -> None:
    """The refusals mtools and nemik agreed: any one of them leaves the umbrella unnamed."""
    open_kid = _umbrella(
        tmp_path, "b", [_top(), _kid("W2", "done"), _kid("W3", "ready")]
    )
    stepped = _umbrella(
        tmp_path, "c", [_top(next_bounded_step="finish it"), _kid("W2", "done")]
    )
    working = _umbrella(tmp_path, "d", [_top(status="working"), _kid("W2", "done")])
    foreign = _umbrella(
        tmp_path,
        "e",
        [
            _top(status="blocked", blocked_on=["other:W9"], blocked_kind="agent"),
            _kid("W2", "done"),
        ],
    )
    foreign += _umbrella(
        tmp_path, "other", [{"symbol": "W9", "title": "far", "status": "ready"}]
    )
    foreign.add((waypoint_uri("e", "W1"), NEMIK.waitsFor, waypoint_uri("other", "W9")))
    assert not _flagged(open_kid, "b")
    assert not _flagged(stepped, "c")
    assert not _flagged(working, "d")
    assert not _flagged(foreign, "e")


def test_a_card_with_its_own_manifest_is_told_to_check_it_not_to_close(
    tmp_path: Path,
) -> None:
    """nemik:W737 (mtools:W1717): done children do not show the card's own files exist."""
    own = _umbrella(
        tmp_path,
        "f",
        [_top(manifest=["src/nemik/x.py"]), _kid("W2", "done"), _kid("W3", "done")],
    )
    assert not _flagged(own, "f")
    assert _flagged(own, "f", "check the manifest before closing it")
    plain = _umbrella(tmp_path, "g", [_top(), _kid("W2", "done")])
    assert _flagged(plain, "g")
    assert not _flagged(plain, "g", "check the manifest before closing it")
