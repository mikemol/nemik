# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W423: the Python half of the pieces conformance run (the TypeScript half is mtools:W1072).

Every case in tests/corpus/pieces is run through nemik.pieces; any difference is printed field by
field, the report github-8f asked for, rather than a bare pass or fail.
"""

import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from nemik.pieces import GraphDoc, assemble, split

CORPUS = Path(__file__).parent / "corpus" / "pieces"
CASES = sorted(CORPUS.glob("*.json"))
MIN_CASES = 5


class _Node(TypedDict):
    """A node of a corpus document, as far as the identity test sorts it."""

    id: str


class _Edge(TypedDict):
    """An edge of a corpus document."""

    source: str
    target: str
    kind: str


class _Doc(TypedDict):
    """A corpus document, as far as the identity test reads it."""

    nodes: list[_Node]
    edges: list[_Edge]
    findings: dict[str, object]
    health: dict[str, object]


def _node_id(node: _Node) -> str:
    """Order nodes by id.

    Args:
        node: The node.

    Returns:
        The node's id.

    """
    return node["id"]


def _edge_key(edge: _Edge) -> tuple[str, str, str]:
    """Order edges by source, target and kind.

    Args:
        edge: The edge.

    Returns:
        The edge's source, target and kind.

    """
    return (edge["source"], edge["target"], edge["kind"])


def _diff(path: str, want: object, got: object) -> list[str]:
    if isinstance(want, dict) and isinstance(got, dict):
        wants = cast("dict[str, object]", want)
        gots = cast("dict[str, object]", got)
        out: list[str] = []
        for k in sorted(set(wants) | set(gots)):
            if k not in gots:
                out.append(f"{path}.{k}: missing")
            elif k not in wants:
                out.append(f"{path}.{k}: unexpected")
            else:
                out += _diff(f"{path}.{k}", wants[k], gots[k])
        return out
    if isinstance(want, list) and isinstance(got, list) and len(want) == len(got):
        want_items = cast("list[object]", want)
        got_items = cast("list[object]", got)
        return [
            d
            for i, (a, b) in enumerate(zip(want_items, got_items, strict=True))
            for d in _diff(f"{path}[{i}]", a, b)
        ]
    return [] if want == got else [f"{path}: want {want!r}, got {got!r}"]


def test_the_corpus_is_there() -> None:
    """The corpus is there."""
    assert len(CASES) >= MIN_CASES


@pytest.mark.parametrize("case", CASES, ids=[p.stem for p in CASES])
def test_python_agrees_with_the_corpus(case: Path) -> None:
    """Python agrees with the corpus."""
    c: dict[str, object] = json.loads(case.read_text(encoding="utf-8"))
    cut = split(cast("GraphDoc", c["doc"]))
    got_split: object = json.loads(json.dumps(cut, default=str))
    back = assemble(cast("dict[str, GraphDoc]", got_split))
    got_back: object = json.loads(json.dumps(back, default=str))
    diffs = _diff("split", c["split"], got_split) + _diff(
        "assemble", c["assemble"], got_back
    )
    assert not diffs, "\n".join(diffs)


@pytest.mark.parametrize("case", CASES, ids=[p.stem for p in CASES])
def test_split_then_assemble_is_identity(case: Path) -> None:
    """Split then assemble is identity."""
    c: dict[str, object] = json.loads(case.read_text(encoding="utf-8"))
    doc = cast("_Doc", dict(cast("dict[str, object]", c["doc"])))
    # assemble's canonical order: nodes by id, edges by (source, target, kind)
    doc["nodes"] = sorted(doc["nodes"], key=_node_id)
    doc["edges"] = sorted(doc["edges"], key=_edge_key)
    doc["findings"] = dict(sorted(doc["findings"].items()))
    doc["health"] = dict(sorted(doc["health"].items()))
    assert c["assemble"] == doc
