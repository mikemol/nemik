# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W154: the field manifest covers every field the export renders and flags a new one."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest

from nemik.apischema import load, unmanifested
from nemik.rank import goals
from nemik.score import load_weights
from nemik.serve import Model
from nemik.wake import operator_row, read_liveness, roster

if TYPE_CHECKING:
    from collections.abc import Iterator

FLEET = Path(__file__).parent / "fixtures" / "fleet"


class _Decoder(Protocol):
    def decode(self, s: str) -> object: ...


def _obj(value: object) -> dict[str, object]:
    """Read a JSON value that must be an object, keyed by text.

    Returns:
        The object's members.

    Raises:
        TypeError: When the value is not an object.

    """
    if not isinstance(value, dict):
        message = f"no object, only {value!r}"
        raise TypeError(message)
    return {str(k): v for k, v in value.items()}


def _list(value: object) -> list[object]:
    """Read a JSON value that must be an array.

    Returns:
        The array's elements.

    Raises:
        TypeError: When the value is not an array.

    """
    if not isinstance(value, list):
        message = f"no array, only {value!r}"
        raise TypeError(message)
    listed: list[object] = list(value)
    return listed


def _documents() -> Iterator[tuple[str, object]]:
    """Yield each document the server publishes, as the JSON it sends.

    Yields:
        (file name, document) pairs: the graph, the wake board and one goals file per repo.

    """
    m = Model(FLEET)
    m.refresh()
    live, source = read_liveness(FLEET, None)
    decoder: _Decoder = json.JSONDecoder()
    graph = _obj(decoder.decode(m.payload.decode()))
    yield "graph.json", graph
    yield (
        "wake.json",
        {
            "liveness": source,
            "roster": roster(m.graph, live),
            "operator": operator_row(m.graph),
        },
    )
    for repo in sorted({str(_obj(n)["repo"]) for n in _list(graph["nodes"])}):
        yield f"goals/{repo}.json", goals(m.graph, repo, load_weights())


def test_every_rendered_field_is_manifested() -> None:
    """Every rendered field is manifested."""
    for name, doc in _documents():
        assert unmanifested(name, doc) == [], name


def test_a_new_field_is_flagged() -> None:
    """A new field is flagged."""
    docs = dict(_documents())
    graph = _obj(docs["graph.json"])
    first = {**_obj(_list(graph["nodes"])[0]), "extra_field": "x"}
    flagged = {**graph, "nodes": [first]}
    assert unmanifested("graph.json", flagged) == ["graph.json nodes.extra_field"]
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
