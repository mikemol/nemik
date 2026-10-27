# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W441: every document the static build publishes validates against the schema it publishes."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("static")
    withheld = tmp / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp / "out"
    build_static(FLEET, out, withheld)
    return out


def _schema_for(name: str) -> str:
    """The published schema path for a published data path (goals/<repo>.json share one)."""
    if name.startswith("goals/"):
        return "schema/goals/repo.json.schema.json"
    return f"schema/{name}.schema.json"


def test_every_schema_is_a_valid_2020_12_schema(built: Path) -> None:
    schemas = list((built / "schema").rglob("*.schema.json"))
    assert schemas
    for p in schemas:
        Draft202012Validator.check_schema(json.loads(p.read_text()))


def test_every_contracted_document_validates(built: Path) -> None:
    checked = 0
    for doc in sorted(built.rglob("*.json")):
        name = str(doc.relative_to(built))
        schema = built / _schema_for(name)
        if name.startswith(("schema/", "graph/")) or name in (
            "hashes.json",
            "openapi.json",
        ):
            # the contract itself (schemas, openapi), pieces cut from graph.json (W415), the index
            continue
        assert schema.exists(), f"{name} is published with no schema"
        validator = Draft202012Validator(json.loads(schema.read_text()))
        errors = sorted(validator.iter_errors(json.loads(doc.read_text())), key=str)
        assert not errors, f"{name}: " + "; ".join(
            f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in errors[:5]
        )
        checked += 1
    assert checked >= 4
