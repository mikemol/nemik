"""nemik:W440: a JSON Schema per published file, generated from field-manifest.json.

The manifest already decides what may be published (nemik:W154: a field outside it fails the build), so it
is the contract; this module only writes it in a form another program can read. Record fields and their
classes come from the manifest; the one thing it does not say is how a file arranges its records (a list,
a map keyed by repo, a single record), so that layout is declared here, per file, once, as measured on the
documents the static build publishes. A record allows no field the manifest does not list.

`$id` carries the manifest's version, so a client can tell which contract it was written against.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from nemik.manifest import load

DIALECT = "https://json-schema.org/draft/2020-12/schema"

# A field class (the manifest's vocabulary) as a JSON Schema fragment.
SCALAR: dict[str, dict[str, Any]] = {
    # nemik:W441: an absent reference is published as null (a goal with nothing on deck), not omitted
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


def field(cls: str) -> dict[str, Any]:
    """The schema of one field class; `list-X` is an array of X."""
    if cls.startswith("list-"):
        return {"type": "array", "items": field(cls.removeprefix("list-"))}
    return SCALAR[cls]


def record(fields: dict[str, str]) -> dict[str, Any]:
    """An object holding only the manifest's fields for it (none required: absent means unknown)."""
    return {
        "type": "object",
        "properties": {name: field(cls) for name, cls in sorted(fields.items())},
        "additionalProperties": False,
    }


def _list(fields: dict[str, str]) -> dict[str, Any]:
    return {"type": "array", "items": record(fields)}


def _by_repo(value: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": value}


def schemas() -> dict[str, dict[str, Any]]:
    """{published path pattern: its schema}, from the manifest."""
    m = load()
    version = json.loads(
        files("nemik.data").joinpath("field-manifest.json").read_text()
    )["version"]
    g, w, h, goals = (
        m["graph.json"],
        m["wake.json"],
        m["history.json"],
        m["goals/<repo>.json"],
    )
    # findings: per repo, a list of findings, each a list of strings (severity, focus, message)
    finding = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}
    bodies: dict[str, dict[str, Any]] = {
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
                "roster": {
                    "type": "array",
                    "items": record(w["roster"])
                    | {
                        "properties": record(w["roster"])["properties"]
                        | {"waiting": _list(w["waiting"])}
                    },
                },
                "operator": record(w["operator"])
                | {
                    "properties": record(w["operator"])["properties"]
                    | {"waiting": _list(w["waiting"])}
                },
            },
            "additionalProperties": False,
        },
        "history.json": _by_repo(_list(h["weeks"])),
        "goals/<repo>.json": _list(goals["goals"]),
    }
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
    """Where the static build publishes the schema for a data path pattern."""
    return "schema/" + pattern.replace("<repo>", "repo") + ".schema.json"


def openapi() -> dict[str, Any]:
    """nemik:W442: the read API as OpenAPI 3.1, generated, so it cannot drift from the schemas.

    Every published data path is a GET whose 200 response refers to the schema the same build
    publishes beside it (OpenAPI 3.1 takes JSON Schema 2020-12 as is). hashes.json and the graph pieces
    (W414, W415) are listed for the client that refetches only what changed.
    """
    version = json.loads(
        files("nemik.data").joinpath("field-manifest.json").read_text()
    )["version"]

    def get(
        summary: str, schema: dict[str, Any], param: str | None = None
    ) -> dict[str, Any]:
        op: dict[str, Any] = {
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

    paths: dict[str, Any] = {}
    for pattern in schemas():
        url = "/" + pattern.replace("<repo>", "{repo}")
        paths[url] = get(
            f"nemik {pattern}",
            {"$ref": schema_path(pattern)},
            "repo" if "<repo>" in pattern else None,
        )
    paths["/hashes.json"] = get(
        "every published path with the sha256 of its bytes (W414): refetch only what moved",
        {"type": "object", "additionalProperties": {"type": "string"}},
    )
    paths["/graph/{piece}.json"] = get(
        "one repo's piece of graph.json, or _fleet (W415); assembling them gives graph.json",
        {"type": "object"},
        "piece",
    )
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "nemik read API",
            "version": str(version),
            "description": "Read-only. Every document is a static file; the field manifest is the "
            "contract, and a field outside it fails nemik's build.",
        },
        "jsonSchemaDialect": DIALECT,
        "paths": paths,
    }
