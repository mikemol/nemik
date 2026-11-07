# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: the arena schema generator writes exactly what apischema wrote, frozen as fixtures.

fixtures/apischema/apischema-golden.json holds the six outputs of the OLD apischema on the
manifest in fixtures/apischema/apischema-manifest.json, and apischema-cases.json holds nine
mutated manifests with their outputs (a missing or colliding `waiting` field, empty field
sets, odd names, nested list classes, thirty fields in reverse order, a string version). All
of it was written from the old module before it was replaced, as compact `json.dumps` text.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from nemik.schemagen import render, schema_path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "fixtures" / "apischema" / "apischema-golden.json"
MANIFEST = HERE / "fixtures" / "apischema" / "apischema-manifest.json"
MUTATED = HERE / "fixtures" / "apischema" / "apischema-cases.json"
OPENAPI = "openapi.json"


def _read(path: Path) -> dict[str, object]:
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast("dict[str, object]", loaded)


def _by_path(manifest: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in render(manifest):
        path, _, body = line.partition("\t")
        rows[path] = body
    return rows


def test_the_packaged_manifest_renders_the_frozen_schemas_and_openapi() -> None:
    """Six outputs, byte for byte: five schemas and the openapi document."""
    golden = _read(GOLDEN)
    manifest = MANIFEST.read_text(encoding="utf-8")
    got = _by_path(manifest)
    want = cast("dict[str, str]", golden["schemas"])
    assert {p: got[p] for p in want} == want
    assert got[OPENAPI] == golden["openapi"]
    assert sorted(got) == sorted([*want, OPENAPI])


CASES = _read(MUTATED)


@pytest.mark.parametrize("name", list(CASES))
def test_a_mutated_manifest_renders_what_the_old_module_wrote(name: str) -> None:
    """Each mutated manifest gives the frozen outputs, byte for byte."""
    case = cast("dict[str, object]", CASES[name])
    got = _by_path(cast("str", case["manifest"]))
    want = cast("dict[str, str]", case["schemas"])
    assert {p: got[p] for p in want} == want
    assert got[OPENAPI] == case["openapi"]


def test_a_schema_is_published_under_schema_with_a_suffix() -> None:
    """The path of a schema file: the repo placeholder written as repo, suffix .schema.json."""
    assert schema_path("goals/<repo>.json") == "schema/goals/repo.json.schema.json"
    assert schema_path("graph.json") == "schema/graph.json.schema.json"
