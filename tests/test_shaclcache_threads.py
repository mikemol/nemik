# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W339 (gate finding): cached_sparql_parse is safe when two threads survey at once.

The gate caught test_serve_model failing under host load with pyparsing errors mid-parse: two
threads in
the block at once, one saving the other's patch as "the originals", and pyparsing's shared state.
"""

import threading

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.plugins.sparql import processor

from nemik.shaclcache import cached_sparql_parse

QUERY = "SELECT ?o WHERE { ?s <urn:p> ?o }"


def _graph() -> Graph:
    g = Graph()
    for i in range(20):
        g.add((URIRef(f"urn:s{i}"), URIRef("urn:p"), Literal(i)))
    return g


def test_concurrent_blocks_answer_correctly_and_restore_the_originals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent blocks answer correctly and restore the originals."""
    parse, translate = processor.parseQuery, processor.translateQuery
    g = _graph()
    errors: list[object] = []
    counts: list[int] = []
    start = threading.Barrier(8)
    # a failing worker thread reports here, so the main thread can assert on it
    monkeypatch.setattr(threading, "excepthook", lambda a: errors.append(a.exc_value))

    def worker() -> None:
        start.wait(timeout=5)
        for _ in range(10):
            with cached_sparql_parse():
                counts.append(len(list(g.query(QUERY))))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert counts == [20] * 80
    assert processor.parseQuery is parse
    assert processor.translateQuery is translate


def test_a_nested_block_still_answers_and_restores() -> None:
    """A nested block still answers and restores."""
    parse = processor.parseQuery
    g = _graph()
    with cached_sparql_parse():
        with cached_sparql_parse():
            assert len(list(g.query(QUERY))) == 20
        assert len(list(g.query(QUERY))) == 20
    assert processor.parseQuery is parse
