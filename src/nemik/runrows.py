# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W558: the rows of a run log as prov:Activity, for the rows that carry the run-row shape.

A run log (apply-set-runs, reaper-runs, apply-ledger, tier-rehearsal, drum decisions) holds one
JSON row per line. Rows that validate against run-row.schema.json (nemik:W556) become activities
with the fields the schema requires; every other row is counted, not guessed at: the logs are
append-only, so the rows written before a writer migrated stay in them without a `ts` or a `run_id`.

The validator reads the schema file itself and interprets the subset the schema uses (required,
type, minLength, pattern, nested required). jsonschema is a development dependency only, so a test
holds this reader to its verdicts on every shape W534 audited.

`decode` is the one place an untyped value enters; everything after it is `object`, narrowed by
isinstance, which is the boundary a Codon port keeps (nemik:W560).
"""

import json
import re
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import PROV, RDFS, XSD

from nemik.adapter import BASE, NEMIK, bind


def decode(text: str) -> object:
    """Decode one JSON document, the only untyped entry point of this module.

    Args:
        text: The JSON text.

    Returns:
        The decoded value, as an opaque object to narrow.

    """
    value: object = json.loads(text)
    return value


def _schema() -> dict[str, object]:
    """Load the run-row schema that ships with the package.

    Returns:
        The decoded schema object.

    Raises:
        TypeError: When the file does not hold a JSON object.

    """
    loaded = decode(
        files("nemik.data").joinpath("run-row.schema.json").read_text(encoding="utf-8")
    )
    if not isinstance(loaded, dict):
        message = "run-row.schema.json is not a JSON object"
        raise TypeError(message)
    return loaded


SCHEMA = _schema()


def _string_fits(value: object, spec: dict[str, object]) -> bool:
    """Say whether a value is a string satisfying the property's length, pattern and format.

    Args:
        value: The decoded JSON value.
        spec: The property's schema.

    Returns:
        True when it is a string of the right length, pattern and, for date-time, instant.

    """
    if not isinstance(value, str):
        return False
    pattern = spec.get("pattern")
    return (
        len(value) >= int(str(spec.get("minLength", 0)))
        and (not isinstance(pattern, str) or re.search(pattern, value) is not None)
        and (spec.get("format") != "date-time" or _instant(value))
    )


def _fits(value: object, spec: dict[str, object]) -> bool:
    """Say whether a value satisfies one schema property.

    Args:
        value: The decoded JSON value.
        spec: The property's schema.

    Returns:
        True when the type, length, pattern and nested required keys all hold.

    """
    kind = spec.get("type")
    if kind == "string":
        return _string_fits(value, spec)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict) and _object_fits(value, spec)
    return True


def _instant(value: str) -> bool:
    """Say whether a string is an RFC 3339 instant with an offset.

    Args:
        value: The candidate text.

    Returns:
        True when it parses and names an offset (a trailing Z counts).

    """
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _object_fits(value: dict[str, object], spec: dict[str, object]) -> bool:
    """Say whether an object has its required keys and well-typed properties.

    Args:
        value: The decoded object.
        spec: Its schema.

    Returns:
        True when every required key is present and every known property fits.

    """
    required = spec.get("required", [])
    if isinstance(required, list) and any(key not in value for key in required):
        return False
    properties = spec.get("properties", {})
    if not isinstance(properties, dict):
        return True
    return all(
        _fits(value[key], sub)
        for key, sub in properties.items()
        if key in value and isinstance(sub, dict)
    )


def valid(row: object) -> bool:
    """Say whether a decoded row carries the run-row shape.

    Args:
        row: One decoded line of a run log.

    Returns:
        True when it satisfies run-row.schema.json.

    """
    return isinstance(row, dict) and _object_fits(row, SCHEMA)


def _add_activity(graph: Graph, stream: str, row: dict[str, object]) -> None:
    """Add one valid row to the graph as an activity.

    Args:
        graph: The graph to add to.
        stream: The log's name.
        row: A row that `valid` accepted.

    """
    verdict = row["verdict"]
    state = verdict["state"] if isinstance(verdict, dict) else ""
    node = URIRef(f"{BASE}run/{stream}/{row['run_id']}/{row['ts']}")
    graph.add((node, RDF.type, PROV.Activity))
    graph.add((node, NEMIK.stream, Literal(stream)))
    graph.add(
        (node, PROV.startedAtTime, Literal(str(row["ts"]), datatype=XSD.dateTime))
    )
    graph.add((node, NEMIK.trigger, Literal(str(row["trigger"]))))
    graph.add(
        (node, NEMIK.exitCode, Literal(int(str(row["exit"])), datatype=XSD.integer))
    )
    graph.add((node, NEMIK.verdictState, Literal(str(state))))
    if row.get("detail"):
        graph.add((node, RDFS.comment, Literal(str(row["detail"]))))


def run_graph(stream: str, path: Path) -> tuple[Graph, int]:
    """Read one run log into activities.

    Args:
        stream: The log's name, for the activity IRIs (for example apply-set-runs).
        path: The JSON-lines file.

    Returns:
        The graph of valid rows, and the count of rows that are not JSON or lack the shape.

    """
    graph = bind(Graph())
    unmigrated = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = decode(line)
        except ValueError:
            unmigrated += 1
            continue
        if isinstance(row, dict) and valid(row):
            _add_activity(graph, stream, row)
        else:
            unmigrated += 1
    return graph, unmigrated
