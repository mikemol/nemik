# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W154: the field manifest covers every field the export renders and flags a new one."""

from pathlib import Path

import pytest

from nemik.apischema import load, unmanifested
from nemik.rank import goals, load_weights
from nemik.serve import Model
from nemik.wake import operator_row, read_liveness, roster

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _documents():
    m = Model(FLEET)
    m.refresh()
    live, source = read_liveness(FLEET, None)
    yield "graph.json", m.doc
    yield (
        "wake.json",
        {
            "liveness": source,
            "roster": roster(m.graph, live),
            "operator": operator_row(m.graph),
        },
    )
    for repo in sorted({n["repo"] for n in m.doc["nodes"]}):
        yield f"goals/{repo}.json", goals(m.graph, repo, load_weights())


def test_every_rendered_field_is_manifested() -> None:
    """Every rendered field is manifested."""
    for name, doc in _documents():
        assert unmanifested(name, doc) == [], name


def test_a_new_field_is_flagged() -> None:
    """A new field is flagged."""
    docs = dict(_documents())
    docs["graph.json"]["nodes"][0]["secret"] = "x"
    assert unmanifested("graph.json", docs["graph.json"]) == ["graph.json nodes.secret"]
    assert unmanifested("goals/x.json", [{"goal": "W1", "leak": 1}]) == [
        "goals/x.json goals.leak"
    ]
    assert unmanifested("extra.json", {}) == ["extra.json: file is not in the manifest"]


def test_a_missing_section_reads_as_no_fields() -> None:
    """A document without a section carries none of its fields."""
    assert unmanifested("graph.json", {}) == []
    assert unmanifested("wake.json", {"roster": None}) == []


def test_a_wrong_typed_document_is_refused() -> None:
    """A present value of the wrong type raises instead of reading as empty."""
    with pytest.raises(TypeError, match="expected an object"):
        unmanifested("graph.json", [])
    with pytest.raises(TypeError, match="expected an object"):
        unmanifested("graph.json", {"health": []})
    with pytest.raises(TypeError, match="expected an array"):
        unmanifested("history.json", {"2026-W01": {"a": 1}})


def test_manifest_classes_are_known() -> None:
    """Manifest classes are known."""
    known = {
        "ref",
        "enum",
        "count",
        "flag",
        "time",
        "text",
        "counts",
        "records",
        "record",
        "list-ref",
        "list-text",
        "list-time",
    }
    for spec in load().values():
        for fields in spec.values():
            assert set(fields.values()) <= known
