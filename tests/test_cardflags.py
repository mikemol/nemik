# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W714: the plain-edge allBlockersLanded flag equals the one blocks.annotate writes."""

import json
from pathlib import Path

from rdflib import RDF, Graph

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import annotate
from nemik.cardflags import all_blockers_landed
from nemik.rank import ref_of


def _card(symbol: str, status: str, waits: list[str]) -> dict[str, object]:
    """Build one queue entry.

    Args:
        symbol: Its symbol.
        status: Its state.
        waits: The cards it is blocked on.

    Returns:
        The entry.

    """
    return {
        "symbol": symbol,
        "title": f"card {symbol}",
        "status": status,
        "enables": [],
        "blocked_on": waits,
        "blocked_kind": "agent" if waits else None,
    }


def _fleet(root: Path) -> Graph:
    """One repo: W3 waits on done W1 only, W4 on done W1 and open W2, W5 on open W2 only.

    Args:
        root: A scratch directory.

    Returns:
        The graph, annotated by blocks.annotate.

    """
    body: dict[str, object] = {
        "version": 1,
        "counter": 5,
        "project_root": "/fixture/alpha",
        "residue": [],
        "waypoints": [
            _card("W1", "done", []),
            _card("W2", "ready", []),
            _card("W3", "blocked", ["W1"]),
            _card("W4", "blocked", ["W1", "W2"]),
            _card("W5", "blocked", ["W2"]),
        ],
    }
    path = root / "paths-forward.json"
    path.write_text(json.dumps(body))
    g = queue_graph("alpha", path)
    annotate(g)
    return g


def test_the_plain_flag_matches_annotate(tmp_path: Path) -> None:
    """The cards flagged from plain edges are the cards annotate flagged in the graph."""
    g = _fleet(tmp_path)
    nodes = set(g.subjects(OSLC_CM.state, None))
    waits = {
        ref_of(n): [ref_of(t) for t in g.objects(n, NEMIK.waitsFor)] for n in nodes
    }
    cited = {ref_of(n): len(set(g.objects(n, NEMIK.blockedOn))) for n in nodes}
    done = {ref_of(n) for n in nodes if (n, OSLC_CM.state, NEMIK.Done) in g}
    dropped = {ref_of(n) for n in g.subjects(RDF.type, NEMIK.Dropped)}
    plain = all_blockers_landed(waits, cited, done | dropped, done)
    reference = {ref_of(n) for n in g.subjects(NEMIK.allBlockersLanded, None)}
    assert plain == reference == {"alpha:W3"}


def test_a_card_with_no_blockers_is_not_flagged() -> None:
    """Nothing to wait for, nothing stale."""
    assert not all_blockers_landed({"a:W1": []}, {"a:W1": 0}, set(), set())


def test_a_done_card_is_never_flagged() -> None:
    """A finished card waits on nothing, whatever it once waited for."""
    assert not all_blockers_landed({"a:W2": ["a:W1"]}, {"a:W2": 1}, {"a:W1"}, {"a:W2"})
