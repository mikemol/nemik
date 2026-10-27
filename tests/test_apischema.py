# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W440: the published schemas are the field manifest, written as JSON Schema."""

import json
from pathlib import Path

from nemik.apischema import schemas
from nemik.manifest import load
from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _records(node: object) -> list[dict]:
    """Every object schema that pins its properties (a record), anywhere in `node`."""
    out: list[dict] = []
    if isinstance(node, dict):
        if node.get("additionalProperties") is False and "properties" in node:
            out.append(node)
        for v in node.values():
            out += _records(v)
    elif isinstance(node, list):
        for v in node:
            out += _records(v)
    return out


def test_every_manifest_field_is_in_a_schema_and_nothing_else() -> None:
    """The generated schemas name each manifest field and no other."""
    m = load()
    generated = schemas()
    assert set(generated) == set(m)
    for path, sections in m.items():
        declared = {f for fields in sections.values() for f in fields if f != "*"}
        named = {p for r in _records(generated[path]) for p in r["properties"]}
        # every manifest field is described; a schema names only manifest fields or the sections
        # that hold them
        assert declared <= named, (path, sorted(declared - named))
        assert named <= declared | set(sections), (
            path,
            sorted(named - declared - set(sections)),
        )


def test_the_static_build_publishes_one_schema_per_file(tmp_path: Path) -> None:
    """A static build writes one schema document beside each published file."""
    withheld = tmp_path / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    published = sorted(
        str(p.relative_to(out / "schema"))
        for p in (out / "schema").rglob("*.schema.json")
    )
    assert published == sorted(
        p.replace("<repo>", "repo") + ".schema.json" for p in load()
    )
    for p in (out / "schema").rglob("*.schema.json"):
        s = json.loads(p.read_text())
        assert s["$schema"].startswith("https://json-schema.org/")
        assert "/schema/v" in s["$id"]
