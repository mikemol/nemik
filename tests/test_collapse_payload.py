# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W973: the umbrellas document, over a queue where two blocked cards wait on one."""

from typing import TYPE_CHECKING

from queue_cases import make_card, write_queue

from nemik.serve import umbrella_docs, without

if TYPE_CHECKING:
    from pathlib import Path

    from rdflib import Graph


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


def waiters(root: Path, symbols: list[str]) -> Graph:
    """One repo: each of the `symbols` waits on W1, which is itself blocked on W9.

    Returns:
        The repo's graph.

    """
    cards = [make_card("W1", "blocked", ["W9"], []), make_card("W9", "ready", [], [])]
    cards += [make_card(s, "blocked", ["W1"], []) for s in symbols]
    return write_queue(root / "alpha.json", "alpha", cards)


def test_a_withheld_waiter_is_in_no_umbrella_row(tmp_path: Path) -> None:
    """nemik:W969: the umbrella is built over the graph without the withheld card.

    The other waiters still form one, and no row names the withheld card.
    """
    rows = umbrella_docs(
        without(waiters(tmp_path, ["W2", "W3", "W4"]), frozenset({"alpha:W3"}))
    )
    assert {row["card"] for row in rows} == {"alpha:W2", "alpha:W4"}
    assert "alpha:W3" not in str(rows)


def test_a_withheld_blocker_is_in_no_umbrella_row(tmp_path: Path) -> None:
    """With the shared blocker withheld, nothing is left to roll the waiters up under."""
    rows = umbrella_docs(
        without(waiters(tmp_path, ["W2", "W3"]), frozenset({"alpha:W1"}))
    )
    assert rows == []


def test_an_umbrella_over_one_waiter_left_by_a_withheld_card_dissolves(
    tmp_path: Path,
) -> None:
    """The documented behaviour: a withheld waiter takes the umbrella with it when one is left.

    The stronger form (drop any umbrella that had a withheld member even when others remain) is
    not what the build does, and this test does not claim it.
    """
    rows = umbrella_docs(
        without(waiters(tmp_path, ["W2", "W3"]), frozenset({"alpha:W3"}))
    )
    assert rows == []
