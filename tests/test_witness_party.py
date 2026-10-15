# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W520: `nemik-witnesses` is a resolvable party for a card that carries a witness, and only for one.

The paths-forward writer refuses a witnessed card that is ready ("a witness, not a tick, marks it done:
block it on nemik-witnesses") and nemik's reader then flagged that blocker as naming no party. Both
cannot be satisfied; the process that closes the card is the party.
"""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, queue_graph
from nemik.blocks import annotate

WITNESS = 'up{job="x"} == 0'


def _unresolved(tmp_path: Path, cards: list[dict]) -> set[str]:
    queue = tmp_path / "r" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 9,
                "residue": [],
                "waypoints": cards,
            }
        )
    )
    g: Graph = queue_graph("r", queue, frozenset({"r"}))
    annotate(g)
    return {
        str(s).rsplit("/", 1)[-1]
        for s, _, _ in g.triples((None, NEMIK.unresolvedBlocker, None))
    }


def _card(symbol: str, blocked_on: str, **more: str) -> dict:
    return {
        "symbol": symbol,
        "title": symbol,
        "status": "blocked",
        "blocked_on": [blocked_on],
        "blocked_kind": "agent",
        "next_bounded_step": "x",
        **more,
    }


def test_a_witnessed_card_may_be_blocked_on_the_witness_runner(tmp_path: Path) -> None:
    cards = [_card("W1", "nemik-witnesses", witness=WITNESS)]
    assert _unresolved(tmp_path, cards) == set()


def test_a_card_without_a_witness_still_names_no_party(tmp_path: Path) -> None:
    cards = [_card("W1", "nemik-witnesses")]
    assert _unresolved(tmp_path, cards) == {"W1"}


def test_a_witnessed_card_blocked_on_nonsense_is_still_flagged(tmp_path: Path) -> None:
    cards = [_card("W1", "somebody-else", witness=WITNESS)]
    assert _unresolved(tmp_path, cards) == {"W1"}
