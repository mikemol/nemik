# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1263: a card whose evidence has an 'apply loop cannot:' line says so in the graph."""

import json
from pathlib import Path

from rdflib import Literal
from rdflib.namespace import XSD

from nemik.adapter import NEMIK, apply_loop_cannot, queue_graph


def test_a_line_with_a_reason_counts() -> None:
    """The line starts the way the exception is worded and gives a reason and a card."""
    text = "a note\napply loop cannot: needs the operator's key, luthen-observability:W9\nmore"
    assert apply_loop_cannot(text)


def test_a_line_with_no_reason_does_not() -> None:
    """The colon with nothing after it is not an exception."""
    assert not apply_loop_cannot("apply loop cannot:\n")
    assert not apply_loop_cannot("apply loop cannot:   ")


def test_the_phrase_inside_a_sentence_does_not() -> None:
    """The line has to start with the phrase, not carry it mid-sentence."""
    assert not apply_loop_cannot("the apply loop cannot: do it from here")


def test_the_graph_carries_it_for_a_card_that_says_so(tmp_path: Path) -> None:
    """A card with the line gets the predicate; the same card without it does not."""
    cards = [
        {
            "symbol": "W1",
            "title": "says it",
            "status": "blocked",
            "blocked_on": ["operator: act sudo install -d /x"],
            "blocked_kind": "human",
            "evidence": "apply loop cannot: the key is the operator's, luthen:W9",
        },
        {
            "symbol": "W2",
            "title": "does not",
            "status": "blocked",
            "blocked_on": ["operator: act sudo install -d /y"],
            "blocked_kind": "human",
            "evidence": "nothing about a loop",
        },
    ]
    state = {
        "version": 1,
        "project_root": str(tmp_path),
        "counter": 2,
        "residue": [],
        "waypoints": cards,
    }
    path = tmp_path / "paths-forward.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    g = queue_graph("a", path)
    true = Literal("true", datatype=XSD.boolean)
    said = {str(s) for s in g.subjects(NEMIK.applyLoopCannot, true)}
    assert len(said) == 1
    assert next(iter(said)).endswith("W1")
