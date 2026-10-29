# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W423: write the pieces conformance corpus, one JSON file per case.

Each case is {"name", "doc", "split", "assemble"}: the graph document, what nemik.pieces.split gives
for it, and what assemble gives for that split. The corpus is language-neutral data, so the Python
source and its transpiled TypeScript (mtools:W1071/W1072) run the same cases and their outputs are
compared field by field. Regenerate with:

    .venv/bin/python3 tools/gen_pieces_corpus.py

and review the diff: a changed expectation is a semantic change to pieces, not noise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from nemik.pieces import assemble, split
from nemik.serve import Model

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "tests" / "corpus" / "pieces"


def _node(repo: str, sym: str) -> dict[str, str]:
    return {"id": f"urn:nemik:{repo}/{sym}", "repo": repo}


def _edge(a: str, b: str, kind: str = "waits") -> dict[str, str]:
    return {"source": a, "target": b, "kind": kind}


def _doc(
    nodes: list[dict[str, str]], edges: list[dict[str, str]], **extra: object
) -> dict[str, object]:
    return {
        "nodes": nodes,
        "edges": edges,
        "inbound": [],
        "operator": [],
        "findings": {},
        "health": {},
        "ruler": {},
        **extra,
    }


def cases() -> dict[str, dict[str, Any]]:
    a1, b1 = "urn:nemik:a/W1", "urn:nemik:b/W1"
    model = Model(HERE / "tests" / "fixtures" / "fleet")
    model.refresh()
    return {
        "empty-fleet": _doc([], []),
        "single-repo": _doc(
            [_node("a", "W1"), _node("a", "W2")],
            [_edge(a1, "urn:nemik:a/W2")],
            findings={"a": []},
            health={"a": {"status": "ok"}},
        ),
        "cross-repo-edge-and-fleet-node": _doc(
            [_node("a", "W1"), _node("b", "W1"), {"id": "operator", "repo": ""}],
            [_edge("operator", a1), _edge(a1, b1)],
            findings={"a": [], "c": [["Warning", "--", "no queue"]]},
            health={"a": {}, "b": {}},
        ),
        # repos and keys given out of order: the pieces and the assembly sort them
        "key-ordering": _doc(
            [_node("z", "W2"), _node("b", "W1"), _node("z", "W1"), _node("a", "W9")],
            [
                _edge("urn:nemik:z/W2", "urn:nemik:z/W1"),
                _edge(b1, "urn:nemik:a/W9", "enables"),
            ],
            findings={"z": [], "a": []},
            health={"z": {}, "b": {}, "a": {}},
            ruler={"motif": ["·"], "f": ["", "·"]},
        ),
        # Python sorts str by code point; JavaScript's default sort compares UTF-16 code units, so
        # an astral character (a surrogate pair, 0xD83D...) sorts BEFORE U+FFFF there and after it
        # here. The transpiled side needs an explicit code-point comparator (github-8f, nemik:W424).
        "astral-plane-keys": _doc(
            [_node("a", "W￿"), _node("a", "W\U0001f600"), _node("a", "W1")],
            [
                _edge("urn:nemik:a/W\U0001f600", "urn:nemik:a/W1"),
                _edge("urn:nemik:a/W￿", "urn:nemik:a/W1"),
            ],
            findings={"a": []},
        ),
        "fixture-fleet-3-repos": _first_repos(dict(model.doc), 3),
    }


def _first_repos(doc: dict[str, Any], n: int) -> dict[str, Any]:
    """Real data at a reviewable size: the fixture fleet cut to its first `n` repos.

    The whole fleet is 3 MB of JSON; tests/test_pieces.py already runs it in Python.
    """
    keep = sorted({str(x["repo"]) for x in doc["nodes"] if x["repo"]})[:n]
    nodes = [x for x in doc["nodes"] if x["repo"] in keep]
    ids = {x["id"] for x in nodes}
    return doc | {
        "nodes": nodes,
        "edges": [e for e in doc["edges"] if e["source"] in ids and e["target"] in ids],
        "findings": {r: v for r, v in doc["findings"].items() if r in keep},
        "health": {r: v for r, v in doc["health"].items() if r in keep},
        "inbound": [],
        "operator": [],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in cases().items():
        cut = split(doc)
        case = {"name": name, "doc": doc, "split": cut, "assemble": assemble(cut)}
        (OUT / f"{name}.json").write_text(
            json.dumps(case, indent=1, sort_keys=True, default=str) + "\n"
        )
        sys.stdout.write(f"{name}: {len(doc['nodes'])} nodes, {len(cut)} pieces\n")


if __name__ == "__main__":
    main()
