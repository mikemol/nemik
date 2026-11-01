# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W172: luthen's withheld list, failing closed, withholding whole."""

import copy
import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from nemik.apischema import unmanifested
from nemik.serve import Model, static_data
from nemik.withheld import WithheldError, apply, load

FLEET = Path(__file__).parent / "fixtures" / "fleet"


class _Node(TypedDict, total=False):
    """A node of graph.json, as far as these tests read it."""

    id: str
    cite: str
    title: str
    state: str


class _Edge(TypedDict, total=False):
    """An edge of graph.json."""

    source: str
    target: str


class _Ask(TypedDict, total=False):
    """An operator entry of graph.json."""

    ref: str


class _Inbound(TypedDict, total=False):
    """An inbound entry of graph.json."""

    blocked: str


class _Graph(TypedDict, total=False):
    """graph.json, as far as these tests read it."""

    nodes: list[_Node]
    edges: list[_Edge]
    operator: list[_Ask]
    inbound: list[_Inbound]


class _Goal(TypedDict, total=False):
    """One entry of a goals/<repo>.json document."""

    goal: str
    frontier: list[str]


@pytest.fixture(scope="module")
def docs() -> dict[str, object]:
    """Build the static documents of the fixture fleet.

    Returns:
        The documents by path.

    """
    return static_data(Model(FLEET))


def _write(tmp_path: Path, doc: dict[str, object]) -> Path:
    p = tmp_path / "withheld.json"
    p.write_text(json.dumps(doc))
    return p


def test_missing_list_fails(tmp_path: Path) -> None:
    """Missing list fails."""
    with pytest.raises(WithheldError, match="did not run"):
        load(tmp_path / "withheld.json")
    with pytest.raises(WithheldError, match="did not run"):
        load(None)


def test_unknown_version_fails(tmp_path: Path) -> None:
    """Unknown version fails."""
    with pytest.raises(WithheldError, match="unknown version"):
        load(_write(tmp_path, {"version": 2, "items": []}))


def test_empty_list_withholds_nothing(tmp_path: Path, docs: dict[str, object]) -> None:
    """Empty list withholds nothing."""
    kept = cast(
        "dict[str, object]",
        apply(docs, load(_write(tmp_path, {"version": 1, "as_of": "x", "items": []}))),
    )
    assert kept == docs


def test_withheld_item_is_dropped_whole_and_pointers_become_stubs(
    tmp_path: Path, docs: dict[str, object]
) -> None:
    """Withheld item is dropped whole and pointers become stubs."""
    docs = copy.deepcopy(docs)
    g = cast("_Graph", docs["graph.json"])
    # an item something else points at, so a stub must appear
    target = next(
        e["target"]
        for e in g["edges"]
        if e["target"].startswith("https://") or "/" in e["target"]
    )
    node = next(n for n in g["nodes"] if n["id"] == target)
    ref = node["cite"]
    node["title"] = (
        "SENTINEL-withheld-text"  # fixture titles are "repo W<n>", substrings of each other
    )
    out = cast(
        "dict[str, object]",
        apply(
            docs,
            load(
                _write(
                    tmp_path,
                    {
                        "version": 1,
                        "items": [{"ref": ref, "field": "title", "rule": "key-shaped"}],
                    },
                )
            ),
        ),
    )
    og = cast("_Graph", out["graph.json"])
    stub = [n for n in og["nodes"] if n["id"] == target]
    assert len(stub) == 1
    assert stub[0]["title"] == "withheld"
    assert stub[0]["state"] == "withheld"
    assert "SENTINEL-withheld-text" not in json.dumps(out)
    assert all(a["ref"] != ref for a in og["operator"])
    assert all(b["blocked"] != ref for b in og["inbound"])
    for name, doc in out.items():
        assert unmanifested(name, doc) == [], name


def test_goals_entry_is_dropped_when_a_frontier_leaf_is_withheld(
    tmp_path: Path, docs: dict[str, object]
) -> None:
    """luthen-observability, 2026-10-02: a withheld leaf's text rode out under the goals it feeds.

    `outside` is the leaves' blocked_on text, so it carried the leaf's text. The whole entry goes.
    """
    goals = {
        n: cast("list[_Goal]", d) for n, d in docs.items() if n.startswith("goals/")
    }
    name, entry = next(
        (n, e)
        for n, d in goals.items()
        for e in d
        if e["frontier"] and e["frontier"][0] != f"{n[6:-5]}:{e['goal']}"
    )
    leaf = entry["frontier"][0]
    out = cast(
        "dict[str, object]",
        apply(
            docs,
            load(
                _write(
                    tmp_path,
                    {
                        "version": 1,
                        "items": [
                            {
                                "ref": leaf,
                                "field": "blocked_on",
                                "rule": "address-literal",
                            }
                        ],
                    },
                )
            ),
        ),
    )
    assert all(leaf not in e["frontier"] for e in cast("list[_Goal]", out[name]))
    assert any(e["goal"] == entry["goal"] for e in goals[name])  # it was there before
