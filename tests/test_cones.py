# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W643: cones over the input graph decide which cards run in parallel and which chain."""

import json
from pathlib import Path

from nemik.cones import Graph, cone, load, parallel, relation

GRAPH: Graph = {
    "src/a.py": {"src/b.py"},
    "src/b.py": {"src/c.py", "data/x.ttl"},
    "src/c.py": set(),
    "src/d.py": set(),
    "tests/test_a.py": {"src/a.py"},
}


def test_a_cone_follows_imports_and_reads_transitively() -> None:
    """Module a imports b, b imports c and reads x.ttl: a's cone holds all four."""
    assert cone(["src/a.py"], GRAPH) == {
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "data/x.ttl",
    }


def test_a_file_the_graph_does_not_know_is_its_own_cone() -> None:
    """An unknown path stays in the cone and depends on nothing."""
    assert cone(["new/file.py"], GRAPH) == {"new/file.py"}


def test_cards_on_unrelated_files_are_disjoint() -> None:
    """d.py and c.py share nothing: they can be worked in parallel."""
    assert relation(["src/d.py"], ["src/c.py"], GRAPH) == "disjoint"


def test_a_card_that_edits_a_dependency_goes_first() -> None:
    """A edits c.py, which a.py (card B's file) depends on: A first."""
    assert relation(["src/c.py"], ["src/a.py"], GRAPH) == "a-first"
    assert relation(["src/a.py"], ["src/c.py"], GRAPH) == "b-first"


def test_a_declared_read_orders_cards_too() -> None:
    """Editing data/x.ttl, which b.py reads, comes before editing a.py."""
    assert relation(["data/x.ttl"], ["src/a.py"], GRAPH) == "a-first"


def test_parallel_skips_a_card_whose_edit_feeds_an_earlier_pick() -> None:
    """Of [a, c, d], c.py feeds a.py, so only a and d run together."""
    manifests = [["src/a.py"], ["src/c.py"], ["src/d.py"]]
    assert parallel(["A", "C", "D"], manifests, [], GRAPH) == ["A", "D"]


def test_parallel_never_picks_an_unplanned_card_or_one_clashing_with_flight() -> None:
    """An empty manifest is never picked, and a file in flight blocks its dependents."""
    assert parallel(["E", "F"], [[], ["src/a.py"]], ["src/c.py"], GRAPH) == []


def test_the_same_file_in_two_cards_is_unordered() -> None:
    """Both edit c.py: no order settles it."""
    assert relation(["src/c.py"], ["src/c.py"], GRAPH) == "both"


def test_load_reads_modules_and_tests_and_ignores_other_schemas(tmp_path: Path) -> None:
    """graph.json schema 1 merges modules and tests; a missing or other-schema file is empty."""
    doc: dict[str, object] = {
        "schema": 1,
        "modules": {"m.py": {"imports": ["n.py"], "reads": ["d.ttl"]}},
        "tests": {"tests/t.py": {"imports": ["m.py"], "reads": []}},
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load(path) == {"m.py": {"n.py", "d.ttl"}, "tests/t.py": {"m.py"}}
    assert load(tmp_path / "missing.json") == {}
    doc["schema"] = 2
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load(path) == {}
