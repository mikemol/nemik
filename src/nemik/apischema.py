# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W440: a JSON Schema per published file, generated from field-manifest.json.

The manifest already decides what may be published (nemik:W154: a field outside it fails the build),
so it is the contract; this module only writes it in a form another program can read. Record fields
and their classes come from the manifest; the one thing it does not say is how a file arranges its
records (a list, a map keyed by repo, a single record), so that layout is declared in
nemik.schemagen, per file, once, as measured on the documents the static build publishes. A record
allows no field the manifest does not list.

`$id` carries the manifest's version, so a client can tell which contract it was written against.

nemik:W2043: the documents are built by nemik.schemagen on the arena tree and are returned as
compact JSON TEXT. A caller that wants dicts (serve.py, the tests) parses the text with
json.loads; no function here takes or returns a heterogeneous dict. The pinned Codon imports this
module (the census), but `load` and `unmanifested` still read JSON as an untyped object and do not
compile when called (nemik:W2049).
"""

import json
from pathlib import Path

import nemik.manifest
import nemik.schemagen

MANIFEST_PATH = Path(__file__).with_name("data") / "field-manifest.json"
OPENAPI = "openapi.json"


def load() -> nemik.manifest.Manifest:
    """Read the manifest's files section from the packaged field-manifest.json.

    Returns:
        For each published file, the fields each of its sections may carry.

    """
    document: object = json.loads(MANIFEST_PATH.read_text())
    section: nemik.manifest.Manifest = (
        document["files"] if isinstance(document, dict) else {}
    )
    return section


def unmanifested(name: str, doc: object) -> list[str]:
    """`path.field` for every field of `doc` (the parsed published file `name`) not in the manifest.

    Args:
        name: The published path of the file, such as `graph.json`.
        doc: The parsed published file.

    Returns:
        One `name section.field` entry per field the packaged manifest does not list.

    """
    return nemik.manifest.unmanifested(name, doc, load())


def schema_path(pattern: str) -> str:
    """Name where the static build publishes the schema for a data path pattern.

    Returns:
        The path under schema/, with `<repo>` written as `repo` and a .schema.json suffix.

    """
    return nemik.schemagen.schema_path(pattern)


def documents() -> dict[str, str]:
    """Render every schema and the openapi document from the packaged manifest.

    Returns:
        Compact JSON text keyed by published path pattern, and by openapi.json for the API document.

    """
    out: dict[str, str] = {}
    for line in nemik.schemagen.render(MANIFEST_PATH.read_text()):
        path, _, body = line.partition("\t")
        out[path] = body
    return out


def schemas_text() -> dict[str, str]:
    """Give {published path pattern: its JSON Schema as compact JSON text}.

    Returns:
        The schema text of each published data path, keyed by its path pattern.

    """
    return {path: body for path, body in documents().items() if path != OPENAPI}


def openapi_text() -> str:
    """Give the read API as an OpenAPI 3.1 document, as compact JSON text (nemik:W442).

    Returns:
        The document, generated so it cannot drift from the schemas.

    """
    return documents()[OPENAPI]
