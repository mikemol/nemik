# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W415: graph.json's per-repo pieces put back together give graph.json."""

import json
import operator
from pathlib import Path

from nemik.pieces import FLEET, GraphDoc, assemble, split
from nemik.serve import build_static
from nemik.tomlview import strings, table, tables

FLEET_FIXTURE = Path(__file__).parent / "fixtures" / "fleet"


def _piece(path: Path) -> GraphDoc:
    """Read one graph piece as the document it is.

    Returns:
        The parsed piece.

    """
    doc: GraphDoc = json.loads(path.read_text(encoding="utf-8"))
    return doc


def test_published_pieces_assemble_to_the_published_graph(tmp_path: Path) -> None:
    """Published pieces assemble to the published graph."""
    withheld = tmp_path / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp_path / "out"
    build_static(FLEET_FIXTURE, out, withheld)
    whole = _piece(out / "graph.json")
    fleet = _piece(out / "graph" / f"{FLEET}.json")
    repos = strings(fleet["repos"])
    assert repos, "the fixture has repos, so there are repo pieces"
    pieces = {FLEET: fleet} | {r: _piece(out / "graph" / f"{r}.json") for r in repos}
    back = assemble(pieces)
    whole["nodes"] = sorted(tables(whole["nodes"]), key=operator.itemgetter("id"))
    assert back == whole


def test_a_repo_piece_holds_only_that_repo() -> None:
    """A repo piece holds only that repo."""
    doc: GraphDoc = {
        "nodes": [
            {"id": "urn:nemik:a/W1", "repo": "a"},
            {"id": "urn:nemik:b/W1", "repo": "b"},
            {"id": "operator", "repo": ""},
        ],
        "edges": [
            # in the published order: sorted by (source, target, kind)
            {"source": "operator", "target": "urn:nemik:a/W1", "kind": "waits"},
            {"source": "urn:nemik:a/W1", "target": "urn:nemik:b/W1", "kind": "waits"},
        ],
        "inbound": [],
        "operator": [],
        "findings": {"a": [], "c": []},
        "health": {"a": {}, "b": {}},
    }
    pieces = split(doc)
    assert [n["id"] for n in tables(pieces["a"]["nodes"])] == ["urn:nemik:a/W1"]
    assert len(tables(pieces["a"]["edges"])) == 1
    assert set(table(pieces[FLEET]["findings"])) == {"c"}
    expected: GraphDoc = {
        **doc,
        "nodes": sorted(tables(doc["nodes"]), key=operator.itemgetter("id")),
        "findings": {"a": [], "c": []},
        "ruler": {},
    }
    assert assemble(pieces) == expected
