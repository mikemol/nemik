# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W597: a card that claims an operator ruling in prose, with no warrant, is warned."""

import json
from pathlib import Path

from nemik.adapter import queue_graph
from nemik.check import shapes
from nemik.shaclinc import findings
from nemik.warrants import claims_ruling, ruling_words

RULED = "2026-10-13 operator ruling: demand is salience"
WARRANT: dict[str, object] = {
    "@context": {"prov": "http://www.w3.org/ns/prov#"},
    "@id": "urn:nemik:nemik/W1",
    "prov:wasDerivedFrom": {"@id": "file:///t/s.jsonl#u1", "@type": "prov:Entity"},
}


def _messages(tmp_path: Path, card: dict[str, object]) -> list[str]:
    """Run the shapes over a one-card queue.

    Args:
        tmp_path: A scratch directory.
        card: The card's extra fields.

    Returns:
        The result messages.

    """
    residue: list[str] = []
    row: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "next_bounded_step": "x",
        **card,
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/nemik",
        "counter": 1,
        "residue": residue,
        "waypoints": [row],
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(state))
    graph = queue_graph("nemik", path)
    return [message for _, _, message in findings("w597", graph, shapes())]


def test_the_claim_phrases_are_declared_data() -> None:
    """The phrases come from rank-weights.toml, and an absent table means none."""
    assert "operator ruling" in ruling_words()
    assert ruling_words("x = 1\n") == []
    assert ruling_words('[rulings]\nwords = ["Said So"]\n') == ["said so"]


def test_an_open_card_claiming_a_ruling_without_a_warrant_is_warned(
    tmp_path: Path,
) -> None:
    """The prose claim draws the Warning; a warrant on the card, or a done card, does not."""
    claimed: dict[str, object] = {"status": "ready", "evidence": RULED}
    warranted: dict[str, object] = {**claimed, "warrants": [WARRANT]}
    landed: dict[str, object] = {**claimed, "status": "done"}
    assert any("no warrant" in m for m in _messages(tmp_path, claimed))
    assert not any("no warrant" in m for m in _messages(tmp_path, warranted))
    assert not any("no warrant" in m for m in _messages(tmp_path, landed))


def test_a_card_that_claims_nothing_is_left_alone() -> None:
    """Prose without a claim phrase draws nothing."""
    assert not claims_ruling({"status": "ready", "evidence": "measured 12 s"})
    assert claims_ruling({"status": "blocked", "title": "Per the operator: decide"})
