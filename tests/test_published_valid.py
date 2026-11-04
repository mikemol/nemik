# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W441: every document the static build publishes validates against its published schema."""

import json
from pathlib import Path
from typing import cast

import jsonschema
import pytest

from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"
MIN_CHECKED = 4


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the static view once for the module.

    Returns:
        The directory it was built into.

    """
    tmp = tmp_path_factory.mktemp("static")
    withheld = tmp / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp / "out"
    build_static(FLEET, out, withheld)
    return out


def _read(path: Path) -> dict[str, object]:
    """Read a JSON document.

    Returns:
        The document as an object map.

    """
    return cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))


def _schema_for(name: str) -> str:
    """Give the published schema path for a data path (goals/<repo>.json share one).

    Returns:
        The path under schema/.

    """
    if name.startswith("goals/"):
        return "schema/goals/repo.json.schema.json"
    return f"schema/{name}.schema.json"


def test_every_schema_is_a_valid_2020_12_schema(built: Path) -> None:
    """Every schema is a valid 2020 12 schema."""
    schemas = list((built / "schema").rglob("*.schema.json"))
    assert schemas
    for p in schemas:
        jsonschema.Draft202012Validator.check_schema(_read(p))


def test_every_contracted_document_validates(built: Path) -> None:
    """Every contracted document validates."""
    checked = 0
    for doc in sorted(built.rglob("*.json")):
        name = str(doc.relative_to(built))
        schema = built / _schema_for(name)
        if name.startswith(("schema/", "graph/")) or name in {
            "hashes.json",
            "openapi.json",
        }:
            # the contract itself (schemas, openapi), pieces cut from graph.json (W415), the index
            continue
        assert schema.exists(), f"{name} is published with no schema"
        validator = jsonschema.Draft202012Validator(_read(schema))
        errors = sorted(validator.iter_errors(_read(doc)), key=str)
        assert not errors, f"{name}: " + "; ".join(
            f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in errors[:5]
        )
        checked += 1
    assert checked >= MIN_CHECKED
