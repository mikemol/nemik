# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: work's tree readers equal the json.loads readers and name what they skip.

work.py read the queue with json.loads and tomlview until the pinned Codon's refusal of an
`object` bound to a json.loads result (wall 2 of the nemik-work compile). It now reads one
tracker.Tree. The frozen copies below are the old readers, unchanged in what they answer, so the
swap stays a tested equivalence: a generated queue (no real queue is embedded) is read both ways
and every answer must match. Input the old code crashed on or stringified is skipped by the new
code, and each skip is one stderr line, which the edge-case fixture asserts (silence on bad input
is what the tombstone rule forbids).
"""

import json
from typing import TYPE_CHECKING

import pytest

from nemik import work
from nemik.tomlview import strings, table, tables
from nemik.tracker import parse_tree

if TYPE_CHECKING:
    from pathlib import Path

CARDS = 60
DONE_EVERY = 4
WORKING_EVERY = 7
READY_EVERY = 5
BLOCK_EVERY = 3


def _old_working(state: Path) -> list[str]:
    """Read the working cards as work.py did: json.loads and tomlview, frozen.

    Returns:
        The symbols of the cards whose status is working.

    """
    raw: object = json.loads(state.read_text(encoding="utf-8"))
    data = table(raw)
    return [
        str(w["symbol"])
        for w in tables(data.get("waypoints"))
        if w.get("status") == "working"
    ]


def _old_blockers(state: Path, symbol: str) -> tuple[list[str], list[str]]:
    """Read a card's blocked_on as work.py did: json.loads and tomlview, frozen.

    Returns:
        The open entries and the landed ones.

    """
    raw: object = json.loads(state.read_text(encoding="utf-8"))
    data = table(raw)
    cards = {str(w["symbol"]): w for w in tables(data.get("waypoints"))}
    dropped = {str(r["symbol"]) for r in tables(data.get("residue"))}
    entries = strings(cards.get(symbol, {}).get("blocked_on"))
    landed = [
        b
        for b in entries
        if b in dropped or (b in cards and cards[b].get("status") == "done")
    ]
    return [b for b in entries if b not in landed], landed


def _old_named(rows: object) -> set[str]:
    """Read the in-gate answer as work.py did, through the same tomlview helpers, frozen.

    Returns:
        Every waypoint any entry names.

    """
    named: set[str] = set()
    for row in tables(rows):
        named.update(strings(row.get("waypoints")))
    return named


def _queue(path: Path) -> list[str]:
    """Write a generated queue and give every symbol in it.

    Returns:
        The card symbols, then a residue symbol and one that is nowhere.

    """
    cards: list[dict[str, object]] = []
    for n in range(CARDS):
        card: dict[str, object] = {"symbol": f"W{n}"}
        if n % DONE_EVERY == 0:
            card["status"] = "done"
        elif n % WORKING_EVERY == 0:
            card["status"] = "working"
        elif n % READY_EVERY:
            card["status"] = "ready"
        if n % BLOCK_EVERY == 0:
            card["blocked_on"] = [f"W{n - 1}", f"W{n - 2}", "other:W7", "free text"]
        elif n % BLOCK_EVERY == 1:
            card["blocked_on"] = None
        cards.append(card)
    # A repeated symbol: the last one wins, in the old readers and the new.
    cards.append({"symbol": "W3", "status": "working"})
    doc = {
        "waypoints": cards,
        "residue": [{"symbol": "W900"}, {"symbol": "W901"}],
        "other": {"nested": [1, 2.5, None, True, "x"]},
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return [*(f"W{n}" for n in range(CARDS)), "W900", "W404"]


def test_the_tree_readers_equal_the_frozen_json_readers(tmp_path: Path) -> None:
    """Agree with the old readers on every symbol of a generated queue."""
    state = tmp_path / "queue.json"
    symbols = _queue(state)
    assert work.working(state) == _old_working(state)
    assert work.working(state)
    for symbol in symbols:
        assert work.blockers(state, symbol) == _old_blockers(state, symbol)


def test_named_waypoints_equals_the_frozen_reader_on_well_formed_answers() -> None:
    """Name what it named for entries, nulls, strangers and an error object."""
    answers: list[object] = [
        [{"waypoints": ["W1"]}, {"waypoints": ["W2", "W3"]}],
        [{"key": "1"}, "W1", None],
        {"error": "x"},
        [],
        [{"waypoints": None}, {"waypoints": []}],
    ]
    for answer in answers:
        tree = parse_tree(json.dumps(answer))
        assert work.named_waypoints(tree) == _old_named(answer)


def test_malformed_input_is_skipped_and_each_skip_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Skip an entry that is not an object, has no string symbol, or a bad member, and say so."""
    doc = {
        "waypoints": [
            {"symbol": "W1", "status": "working", "blocked_on": ["W2", 5, None]},
            "stray",
            {"status": "ready"},
            {"symbol": 7},
            {"symbol": "W2", "status": "done"},
        ],
        "residue": "not an array",
    }
    state = tmp_path / "queue.json"
    state.write_text(json.dumps(doc), encoding="utf-8")
    assert work.working(state) == ["W1"]
    said = capsys.readouterr().err.splitlines()
    assert said == [
        "work: skipped malformed waypoints element 1 (not an object)",
        "work: skipped malformed waypoints element 2 (no string symbol)",
        "work: skipped malformed waypoints element 3 (no string symbol)",
        "work: skipped malformed residue (not an array)",
    ]
    assert work.blockers(state, "W1") == ([], ["W2"])
    said = capsys.readouterr().err.splitlines()
    assert said[-2:] == [
        "work: dropped non-string element of blocked_on of W1",
        "work: dropped non-string element of blocked_on of W1",
    ]


def test_an_absent_or_null_member_is_not_malformed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Say nothing for a queue with a null residue member and a card with a null status."""
    state = tmp_path / "queue.json"
    doc: dict[str, object] = {
        "waypoints": [{"symbol": "W1", "status": None}],
        "residue": None,
    }
    state.write_text(json.dumps(doc), encoding="utf-8")
    assert work.working(state) == []
    assert work.blockers(state, "W1") == ([], [])
    assert not capsys.readouterr().err
