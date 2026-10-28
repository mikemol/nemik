# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W415: graph.json's per-repo pieces put back together give graph.json."""

import json
import operator
from pathlib import Path
from typing import Any

from nemik.pieces import FLEET, assemble, split
from nemik.serve import build_static

FLEET_FIXTURE = Path(__file__).parent / "fixtures" / "fleet"


def test_published_pieces_assemble_to_the_published_graph(tmp_path: Path) -> None:
    withheld = tmp_path / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp_path / "out"
    build_static(FLEET_FIXTURE, out, withheld)
    whole = json.loads((out / "graph.json").read_text())
    fleet = json.loads((out / "graph" / f"{FLEET}.json").read_text())
    assert fleet["repos"], "the fixture has repos, so there are repo pieces"
    pieces = {FLEET: fleet} | {
        r: json.loads((out / "graph" / f"{r}.json").read_text()) for r in fleet["repos"]
    }
    back = assemble(pieces)
    whole["nodes"] = sorted(whole["nodes"], key=operator.itemgetter("id"))
    assert back == whole


def test_a_repo_piece_holds_only_that_repo() -> None:
    doc: dict[str, Any] = {
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
    assert [n["id"] for n in pieces["a"]["nodes"]] == ["urn:nemik:a/W1"]
    assert len(pieces["a"]["edges"]) == 1
    assert set(pieces[FLEET]["findings"]) == {"c"}
    assert assemble(pieces) == doc | {
        "nodes": sorted(doc["nodes"], key=operator.itemgetter("id")),
        "findings": {"a": [], "c": []},
        "ruler": {},
    }
