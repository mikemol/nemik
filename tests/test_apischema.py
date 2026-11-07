# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W440: the published schemas are the field manifest, written as JSON Schema."""

import json
from pathlib import Path

from nemik.apischema import load, openapi_text, schemas_text
from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _record_names(node: object) -> list[str]:
    """Every property name of every object schema that pins its properties, anywhere in `node`.

    Returns:
        The names found, in walk order.

    """
    out: list[str] = []
    if isinstance(node, dict):
        if node.get("additionalProperties") is False and "properties" in node:
            props: dict[str, object] = node["properties"]
            out.extend(props)
        for v in node.values():
            out += _record_names(v)
    elif isinstance(node, list):
        for v in node:
            out += _record_names(v)
    return out


def _parse(text: str) -> object:
    """Parse JSON text into plain data.

    Returns:
        The document.

    """
    parsed: object = json.loads(text)
    return parsed


def test_every_manifest_field_is_in_a_schema_and_nothing_else() -> None:
    """The generated schemas name each manifest field and no other."""
    m = load()
    generated = {path: _parse(text) for path, text in schemas_text().items()}
    assert set(generated) == set(m)
    for path, sections in m.items():
        declared = {f for fields in sections.values() for f in fields if f != "*"}
        named = set(_record_names(generated[path]))
        # every manifest field is described; a schema names only manifest fields or the sections
        # that hold them
        assert declared <= named, (path, sorted(declared - named))
        assert named <= declared | set(sections), (
            path,
            sorted(named - declared - set(sections)),
        )


def test_the_openapi_text_is_a_compact_json_document_of_the_read_api() -> None:
    """openapi_text parses to an OpenAPI 3.1 document whose paths include every schema pattern."""
    api: dict[str, object] = json.loads(openapi_text())
    assert api["openapi"] == "3.1.0"
    paths = api["paths"]
    assert isinstance(paths, dict)
    for pattern in schemas_text():
        assert "/" + pattern.replace("<repo>", "{repo}") in paths


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
        s: dict[str, str] = json.loads(p.read_text())
        assert s["$schema"].startswith("https://json-schema.org/")
        assert "/schema/v" in s["$id"]
