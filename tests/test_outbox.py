# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W354: a repo's cards render as a read-only ForgeFed outbox."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph, waypoint_uri
from nemik.outbox import outbox


def _queue(tmp_path: Path) -> Graph:
    """Read a queue with one card per state.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [
        {"symbol": "W1", "title": "offered", "status": "ready"},
        {"symbol": "W2", "title": "taken", "status": "working"},
        {"symbol": "W3", "title": "finished", "status": "done"},
    ]
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


def test_state_is_a_property_and_the_verb_is_the_event(tmp_path: Path) -> None:
    """Each Ticket says isResolved and its tracker; a minting is a Create, a closing a Resolve."""
    text = outbox("a", _queue(tmp_path))
    lines = text.splitlines()
    verbs = [ln.split('"')[3] for ln in lines if '"type": "' in ln]
    assert [v for v in verbs if v in {"Create", "Resolve"}] == [
        "Create",
        "Create",
        "Resolve",
    ]
    assert [ln.split(": ")[1] for ln in lines if '"isResolved"' in ln] == [
        "false,",
        "false,",
        "true,",
    ]
    assert len({ln for ln in lines if '"context"' in ln}) == 1
    assert "Offer" not in text
    assert "Accept" not in text
    assert '"type": "OrderedCollection"' in text
    assert "https://forgefed.org/ns" in text
    assert '"totalItems": 3' in text


def test_a_ticket_carries_its_edges(tmp_path: Path) -> None:
    """A wait on a card is dependsOn and an enable dependedBy; the operator is no Ticket."""
    cards: list[dict[str, object]] = [
        {
            "symbol": "W1",
            "title": "waiting",
            "status": "blocked",
            "blocked_on": ["W2", "operator: decide x"],
            "enables": ["W3"],
        },
        {"symbol": "W2", "title": "waited", "status": "ready"},
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 3,
        "residue": [],
        "waypoints": cards,
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    text = outbox("a", queue_graph("a", path))
    lines = [ln.strip() for ln in text.splitlines()]
    assert lines.count('"urn:nemik:a/W2"') == 1
    assert lines.count('"urn:nemik:a/W3"') == 1
    assert '"dependsOn": [' in lines
    assert '"dependedBy": [' in lines
    assert text.count('"dependsOn"') == 1
    assert "operator" not in text


def test_a_resolved_ticket_says_when(tmp_path: Path) -> None:
    """A done card's Ticket carries `resolved`, its last work; an open card's carries none."""
    cards: list[dict[str, object]] = [
        {
            "symbol": "W1",
            "title": "closed",
            "status": "done",
            "last_worked": "2026-10-02T03:04:05Z",
        },
        {"symbol": "W2", "title": "open", "status": "ready"},
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 2,
        "residue": [],
        "waypoints": cards,
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    text = outbox("a", queue_graph("a", path))
    stamps = [ln.split('"')[3] for ln in text.splitlines() if '"resolved"' in ln]
    assert stamps == ["2026-10-02T03:04:05+00:00"]


def test_an_activity_is_published_when_the_card_was_last_worked(tmp_path: Path) -> None:
    """A worked card's time is its last work; a card never worked falls back to its issue time."""
    cards: list[dict[str, object]] = [
        {
            "symbol": "W1",
            "title": "worked",
            "status": "done",
            "issued_at": "2026-10-01T00:00:00Z",
            "last_worked": "2026-10-02T03:04:05Z",
        },
        {
            "symbol": "W2",
            "title": "idle",
            "status": "ready",
            "issued_at": "2026-10-01T06:00:00Z",
        },
        {"symbol": "W3", "title": "undated", "status": "ready"},
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 3,
        "residue": [],
        "waypoints": cards,
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    text = outbox("a", queue_graph("a", path))
    stamps = [line.split('"')[3] for line in text.splitlines() if '"published"' in line]
    assert stamps == ["2026-10-02T03:04:05+00:00", "2026-10-01T06:00:00+00:00"]


def test_a_withheld_card_leaves_the_document_whole(tmp_path: Path) -> None:
    """Withholding W2 removes its activity and its title from the bytes."""
    hidden = frozenset({str(waypoint_uri("a", "W2"))})
    text = outbox("a", _queue(tmp_path), hidden)
    assert "taken" not in text
    assert '"totalItems": 2' in text
