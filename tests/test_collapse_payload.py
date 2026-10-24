# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W973: the umbrellas document, over a queue where two blocked cards wait on one."""

from pathlib import Path

from queue_cases import make_card, write_queue
from rdflib import Graph

from nemik.serve import umbrella_docs


def graph(root: Path) -> Graph:
    """One repo: W2 and W3 wait on W1, which is itself blocked on W9.

    Returns:
        The repo's graph.

    """
    cards = [
        make_card("W1", "blocked", ["W9"], []),
        make_card("W2", "blocked", ["W1"], []),
        make_card("W3", "blocked", ["W1"], []),
        make_card("W9", "ready", [], []),
    ]
    return write_queue(root / "alpha.json", "alpha", cards)


def test_two_waiters_form_an_umbrella(tmp_path: Path) -> None:
    """The umbrella names its blocker and holds both waiters under n-path addresses."""
    docs = umbrella_docs(graph(tmp_path))
    name = docs[0]["id"]
    assert docs == [
        {
            "id": name,
            "blockers": ["alpha:W1"],
            "enables": [],
            "card": card,
            "address": f"{name}/{card}",
        }
        for card in ("alpha:W2", "alpha:W3")
    ]


def test_no_blocked_pair_means_no_umbrella(tmp_path: Path) -> None:
    """A queue with one waiter per blocker rolls up nothing."""
    cards = [make_card("W1", "blocked", ["W9"], []), make_card("W9", "ready", [], [])]
    assert umbrella_docs(write_queue(tmp_path / "alpha.json", "alpha", cards)) == []
