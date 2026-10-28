# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W172: luthen's withheld list, failing closed, withholding whole."""

import json
from pathlib import Path

import pytest

from nemik.manifest import unmanifested
from nemik.serve import Model, static_data
from nemik.withheld import WithheldError, apply, load

FLEET = Path(__file__).parent / "fixtures" / "fleet"


@pytest.fixture(scope="module")
def docs() -> dict[str, object]:
    return static_data(Model(FLEET))


def _write(tmp_path: Path, doc: dict[str, object]) -> Path:
    p = tmp_path / "withheld.json"
    p.write_text(json.dumps(doc))
    return p


def test_missing_list_fails(tmp_path: Path) -> None:
    with pytest.raises(WithheldError, match="did not run"):
        load(tmp_path / "withheld.json")
    with pytest.raises(WithheldError, match="did not run"):
        load(None)


def test_unknown_version_fails(tmp_path: Path) -> None:
    with pytest.raises(WithheldError, match="unknown version"):
        load(_write(tmp_path, {"version": 2, "items": []}))


def test_empty_list_withholds_nothing(tmp_path: Path, docs: dict[str, object]) -> None:
    assert (
        apply(docs, load(_write(tmp_path, {"version": 1, "as_of": "x", "items": []})))
        == docs
    )


def test_withheld_item_is_dropped_whole_and_pointers_become_stubs(
    tmp_path, docs
) -> None:
    import copy

    docs = copy.deepcopy(docs)
    g = docs["graph.json"]
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
    out = apply(
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
    )
    og = out["graph.json"]
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
    tmp_path, docs
) -> None:
    """luthen-observability, 2026-10-02: `outside` is the leaves' blocked_on text, so a withheld
    leaf's text rode out under the goals it feeds. The whole entry goes.
    """
    name, entry = next(
        (n, e)
        for n, d in docs.items()
        if n.startswith("goals/")
        for e in d
        if e["frontier"] and e["frontier"][0] != f"{n[6:-5]}:{e['goal']}"
    )
    leaf = entry["frontier"][0]
    out = apply(
        docs,
        load(
            _write(
                tmp_path,
                {
                    "version": 1,
                    "items": [
                        {"ref": leaf, "field": "blocked_on", "rule": "address-literal"}
                    ],
                },
            )
        ),
    )
    assert all(leaf not in e["frontier"] for e in out[name])
    assert any(e["goal"] == entry["goal"] for e in docs[name])  # it was there before
