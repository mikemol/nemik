# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W440: a JSON Schema per published file, generated from field-manifest.json.

The manifest already decides what may be published (nemik:W154: a field outside it fails the build),
so it is the contract; this module only writes it in a form another program can read. Record fields
and their classes come from the manifest; the one thing it does not say is how a file arranges its
records (a list, a map keyed by repo, a single record), so that layout is declared here, per file,
once, as measured on the documents the static build publishes. A record allows no field the manifest
does not list.

`$id` carries the manifest's version, so a client can tell which contract it was written against.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TYPE_CHECKING

from nemik import manifest

if TYPE_CHECKING:
    from nemik.manifest import Manifest

DIALECT = "https://json-schema.org/draft/2020-12/schema"

# A JSON Schema fragment, or any JSON object: values are read only by the json module.
Schema = dict[str, object]
# A field class (the manifest's vocabulary) as a JSON Schema fragment.
SCALAR: dict[str, Schema] = {
    # nemik:W441: an absent reference is published as null (a goal with nothing on deck), not
    # omitted
    "ref": {"type": ["string", "null"]},
    "enum": {"type": "string"},
    "text": {"type": "string"},
    "time": {"type": ["string", "null"]},
    "count": {"type": ["number", "null"]},
    "flag": {"type": "boolean"},
    "counts": {"type": "object", "additionalProperties": {"type": "number"}},
    "records": {"type": "array", "items": {"type": "object"}},
    "record": {"type": ["object", "null"]},
}


def load() -> Manifest:
    """Read the manifest's files section from the packaged field-manifest.json.

    Returns:
        For each published file, the fields each of its sections may carry.

    """
    document: object = json.loads(
        files("nemik.data").joinpath("field-manifest.json").read_text()
    )
    section: Manifest = document["files"] if isinstance(document, dict) else {}
    return section


def unmanifested(name: str, doc: object, m: Manifest | None = None) -> list[str]:
    """`path.field` for every field of `doc` (the parsed published file `name`) not in the manifest.

    Args:
        name: The published path of the file, such as `graph.json`.
        doc: The parsed published file.
        m: The manifest's files section; None reads the packaged one.

    Returns:
        One `name section.field` entry per field the manifest does not list.

    """
    return manifest.unmanifested(name, doc, m or load())


def field(cls: str) -> Schema:
    """Give the schema of one field class; `list-X` is an array of X.

    Returns:
        An array schema of the inner class's schema for `list-X`, else the scalar's schema.

    """
    if cls.startswith("list-"):
        return {"type": "array", "items": field(cls.removeprefix("list-"))}
    return SCALAR[cls]


def record(fields: dict[str, str]) -> Schema:
    """Give an object of only the manifest's fields for it (none required: absent means unknown).

    Returns:
        An object schema with a property per field, sorted by name, and no other property allowed.

    """
    return {
        "type": "object",
        "properties": {name: field(cls) for name, cls in sorted(fields.items())},
        "additionalProperties": False,
    }


def _list(fields: dict[str, str]) -> Schema:
    return {"type": "array", "items": record(fields)}


def _by_repo(value: Schema) -> Schema:
    return {"type": "object", "additionalProperties": value}


def _waiting(fields: dict[str, str], waiting: dict[str, str]) -> Schema:
    # a record whose properties also carry `waiting`, a list of the waiting records
    properties = {name: field(cls) for name, cls in sorted(fields.items())}
    return record(fields) | {"properties": properties | {"waiting": _list(waiting)}}


def _version() -> str:
    # the manifest's version, which the schemas' `$id` carries
    document: object = json.loads(
        files("nemik.data").joinpath("field-manifest.json").read_text()
    )
    return str(document["version"]) if isinstance(document, dict) else ""


def schemas() -> dict[str, Schema]:
    """Give {published path pattern: its schema}, from the manifest.

    Returns:
        The schema of each published data path, keyed by its path pattern.

    """
    m: Manifest = load()
    version = _version()
    g, w, h = (m["graph.json"], m["wake.json"], m["history.json"])
    # findings: per repo, a list of findings, each a list of strings (severity, focus, message)
    finding: Schema = {
        "type": "array",
        "items": {"type": "array", "items": {"type": "string"}},
    }
    bodies: dict[str, Schema] = {
        "graph.json": {
            "type": "object",
            "properties": {
                "nodes": _list(g["nodes"]),
                "edges": _list(g["edges"]),
                "inbound": _list(g["inbound"]),
                "operator": _list(g["operator"]),
                "findings": _by_repo(finding),
                "health": _by_repo(record(g["health"])),
                "ruler": record(g["ruler"]),
            },
            "required": ["nodes", "edges"],
            "additionalProperties": False,
        },
        "wake.json": {
            "type": "object",
            "properties": {
                "liveness": field(w["top"]["liveness"]),
                "series": SCALAR["record"],
                "roster": {
                    "type": "array",
                    "items": _waiting(w["roster"], w["waiting"]),
                },
                "operator": _waiting(w["operator"], w["waiting"]),
            },
            "additionalProperties": False,
        },
        "history.json": _by_repo(_list(h["weeks"])),
    }
    # the files that are one flat list of records, each under one manifest section
    flat = (("goals/<repo>.json", "goals"), ("umbrellas.json", "umbrellas"))
    for path, section in flat:
        bodies[path] = _list(m[path][section])
    return {
        path: {
            "$schema": DIALECT,
            "$id": f"https://nemik/schema/v{version}/{path.replace('<repo>', '{repo}')}",
            "title": f"nemik {path}",
        }
        | body
        for path, body in bodies.items()
    }


def schema_path(pattern: str) -> str:
    """Where the static build publishes the schema for a data path pattern.

    Returns:
        The path under schema/, with `<repo>` written as `repo` and a .schema.json suffix.

    """
    return "schema/" + pattern.replace("<repo>", "repo") + ".schema.json"


def _get(summary: str, schema: Schema, param: str | None = None) -> Schema:
    op: Schema = {
        "summary": summary,
        "responses": {
            "200": {
                "description": "the document",
                "content": {"application/json": {"schema": schema}},
            }
        },
    }
    if param:
        op["parameters"] = [
            {
                "name": param,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
        ]
    return {"get": op}


def openapi() -> Schema:
    """nemik:W442: the read API as OpenAPI 3.1, generated, so it cannot drift from the schemas.

    Every published data path is a GET whose 200 response refers to the schema the same build
    publishes beside it (OpenAPI 3.1 takes JSON Schema 2020-12 as is). hashes.json and the graph
    pieces (W414, W415) are listed for the client that refetches only what changed.

    Returns:
        The OpenAPI 3.1 document.

    """
    paths: Schema = {}
    for pattern in schemas():
        url = "/" + pattern.replace("<repo>", "{repo}")
        paths[url] = _get(
            f"nemik {pattern}",
            {"$ref": schema_path(pattern)},
            "repo" if "<repo>" in pattern else None,
        )
    paths["/hashes.json"] = _get(
        "every published path with the sha256 of its bytes (W414): refetch only what moved",
        {"type": "object", "additionalProperties": {"type": "string"}},
    )
    paths["/graph/{piece}.json"] = _get(
        "one repo's piece of graph.json, or _fleet (W415); assembling them gives graph.json",
        {"type": "object"},
        "piece",
    )
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "nemik read API",
            "version": _version(),
            "description": "Read-only. Every document is a static file; the field manifest is the "
            "contract, and a field outside it fails nemik's build.",
        },
        "jsonSchemaDialect": DIALECT,
        "paths": paths,
    }
