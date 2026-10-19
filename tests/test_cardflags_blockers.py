# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W714: the plain-edge unresolved-blocker flag equals the one blocks.annotate writes."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import annotate
from nemik.cardflags import unresolved_blockers
from nemik.rank import ref_of


def _card(
    symbol: str, waits: list[str], kind: str, witness: str = ""
) -> dict[str, object]:
    """Build one blocked queue entry.

    Args:
        symbol: Its symbol.
        waits: Its blocked_on entries.
        kind: Its blocked_kind.
        witness: A Rego witness query, or empty for none.

    Returns:
        The entry.

    """
    card: dict[str, object] = {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": "blocked",
        "enables": [],
        "blocked_on": waits,
        "blocked_kind": kind,
    }
    if witness:
        card["witness"] = witness
        card["witness_lang"] = "rego"
    return card


def _fleet(root: Path) -> Graph:
    """One repo with a blocker of each kind: a card, an operator, a condition, prose, witnesses.

    Args:
        root: A scratch directory.

    Returns:
        The graph, annotated by blocks.annotate.

    """
    ready: dict[str, object] = {
        "symbol": "W1",
        "title": "card W1",
        "status": "ready",
        "enables": [],
        "blocked_on": [],
        "blocked_kind": None,
    }
    body: dict[str, object] = {
        "version": 1,
        "counter": 8,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": [
            ready,
            _card("W2", ["W1"], "agent"),
            _card("W3", ["operator: decide which"], "human"),
            _card("W4", ["cal:fixture/abc"], "agent"),
            _card("W5", ["host:home-mount"], "agent"),
            _card("W6", ["some prose nobody can resolve"], "agent"),
            _card("W7", ["nemik-witnesses"], "agent"),
            _card("W8", ["nemik-witnesses"], "agent", "input.file.exists"),
        ],
    }
    path = root / "paths-forward.json"
    path.write_text(json.dumps(body))
    g = queue_graph("alpha", path)
    annotate(g)
    return g


def test_the_plain_flag_matches_annotate(tmp_path: Path) -> None:
    """The same cards and entries are flagged: prose (W6) and a witness-less W7."""
    g = _fleet(tmp_path)
    blocked = set(g.subjects(OSLC_CM.state, NEMIK.Blocked))
    cited = {
        ref_of(n): [str(t) for t in g.objects(n, NEMIK.blockedOn)] for n in blocked
    }
    resolved = {ref_of(n) for n in blocked if (n, NEMIK.waitsFor, None) in g}
    human = {
        ref_of(n) for n in blocked if str(g.value(n, NEMIK.blockedKind)) == "human"
    }
    witnessed = {ref_of(n) for n in blocked if (n, NEMIK.weather, None) in g}
    plain = unresolved_blockers(cited, resolved, human, witnessed)
    reference: dict[str, list[str]] = {}
    for n, _, text in g.triples((None, NEMIK.unresolvedBlocker, None)):
        reference.setdefault(ref_of(n), []).append(str(text))
    assert plain == reference
    assert sorted(plain) == ["alpha:W6", "alpha:W7"]


def test_a_card_that_resolves_is_not_flagged() -> None:
    """A card waiting on a resolvable card, or on a form-resolved condition, is clean."""
    assert not unresolved_blockers({"a:W1": ["cal:x/y"]}, {"a:W2"}, set(), set())
    assert not unresolved_blockers({"a:W2": ["whatever"]}, {"a:W2"}, set(), set())
