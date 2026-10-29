# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W402: a queue or ledger is re-parsed only when its file moved; the caller may mutate."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rdflib import Graph, Literal, URIRef

from nemik import adapter

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _counting(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"n": 0}

    def build(repo: str, path: Path, known: frozenset[str]) -> Graph:
        calls["n"] += 1
        g = Graph()
        g.add(
            (
                URIRef(f"urn:{repo}"),
                URIRef("urn:p"),
                Literal(path.read_text(encoding="utf-8")),
            )
        )
        return g

    monkeypatch.setattr(adapter, "_queue_graph", build)
    monkeypatch.setattr(adapter, "_PARSED", {})
    return calls


def test_an_unchanged_file_is_parsed_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counting(monkeypatch)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text("1")
    b.write_text("1")
    known = frozenset({"a", "b"})
    for _ in range(3):
        adapter.queue_graph("a", a, known)
        adapter.queue_graph("b", b, known)
    assert calls["n"] == 2
    a.write_text("22")
    os.utime(a, ns=(1, 1))
    adapter.queue_graph("a", a, known)
    adapter.queue_graph("b", b, known)
    assert calls["n"] == 3


def test_a_new_repo_invalidates_every_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counting(monkeypatch)
    a = tmp_path / "a.json"
    a.write_text("1")
    adapter.queue_graph("a", a, frozenset({"a"}))
    adapter.queue_graph("a", a, frozenset({"a", "c"}))
    assert calls["n"] == 2


def test_a_mutated_answer_does_not_reach_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _counting(monkeypatch)
    a = tmp_path / "a.json"
    a.write_text("1")
    first = adapter.queue_graph("a", a)
    first.add((URIRef("urn:x"), URIRef("urn:p"), Literal("added")))
    assert len(adapter.queue_graph("a", a)) == 1
