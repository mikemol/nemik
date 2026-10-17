# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W520: a witnessed card blocked on nemik-witnesses names a party; a bare one does not."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph, waypoint_uri
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings


def _queue(tmp_path: Path, witness: str, lang: str) -> Graph:
    """Read a queue whose W1 is blocked on nemik-witnesses, with a witness of a language.

    Args:
        tmp_path: A scratch directory.
        witness: The witness query, or empty for none.
        lang: The witness's declared language.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "blocked",
        "blocked_on": ["nemik-witnesses"],
        "blocked_kind": "agent",
        "witness": witness,
        "witness_lang": lang,
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 1,
        "residue": residue,
        "waypoints": [card],
    }
    path = tmp_path / f"{lang}.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("a", path)


def _unresolved(g: Graph, key: str) -> bool:
    """Say whether W1 draws the no-resolvable-party finding.

    Args:
        g: The queue's graph.
        key: A cache key unique to this graph.

    Returns:
        True when the finding names W1.

    """
    annotate(g)
    node = waypoint_uri("a", "W1")
    rows = findings(key, g, shapes())
    return any(f == node and "no resolvable party" in m for f, _, m in rows)


def test_a_promql_witness_makes_nemik_witnesses_a_party(tmp_path: Path) -> None:
    """Luthen's form: blocked on nemik-witnesses with a promql witness resolves."""
    query = 'count(count_over_time({"mikemol.commit.inflight"}[7d]) >= 40) >= 3'
    assert not _unresolved(_queue(tmp_path, query, "promql"), "witnessed-promql")


def test_a_rego_witness_resolves_too(tmp_path: Path) -> None:
    """The Rego form nemik's own web-vitals cards use resolves the same way."""
    stamp = "2026-10-24T06:26:00Z"
    query = f'time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("{stamp}")'
    assert not _unresolved(_queue(tmp_path, query, "rego"), "witnessed-rego")


def test_nemik_witnesses_without_a_witness_is_still_unresolved(tmp_path: Path) -> None:
    """Naming the observer is not enough: with no witness there is nothing for it to observe."""
    assert _unresolved(_queue(tmp_path, "", "rego"), "unwitnessed")
