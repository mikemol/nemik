# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W154: the field manifest for the static public view.

`data/field-manifest.json` names every field each published file may carry. `unmanifested` returns
the fields a rendered document has that the manifest does not, so the static build (nemik:W153)
fails instead of publishing a field nobody classified (operator 2026-10-01, luthen's withhold-whole
contract). It checks the export's shape, not its values: which items are withheld is luthen's list.

This module is the pure half (nemik:W1179): it takes the manifest as a parsed argument and imports
nothing, like nemik.tiers and nemik.adoption, so the Codon census can compile it. Reading the
manifest file is apischema.load's, and apischema.unmanifested is the call with the packaged one.
"""

# For each published file, the fields each of its sections may carry.
Manifest = dict[str, dict[str, dict[str, str]]]


def _dict(value: object) -> dict[str, object]:
    """Read a parsed JSON value as an object, or an empty one when it is anything else.

    Returns:
        The object's entries, keyed by string.

    """
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    """Read a parsed JSON value as an array, or an empty one when it is anything else.

    Returns:
        The array's elements.

    """
    if isinstance(value, list):
        items: list[object] = value
        return items
    return []


def _fields(rows: object) -> set[str]:
    return {k for r in _list(rows) for k in _dict(r)}


def unmanifested(name: str, doc: object, m: Manifest) -> list[str]:
    """`path.field` for every field of `doc` (the parsed published file `name`) not in `m`.

    Args:
        name: The published path of the file, such as `graph.json` or `goals/<repo>.json`.
        doc: The parsed published file.
        m: The manifest's files section.

    Returns:
        One `name section.field` entry per field the manifest does not list, or one
        entry when the file is not in the manifest.

    """
    key = "goals/<repo>.json" if name.startswith("goals/") else name
    if key not in m:
        return [f"{name}: file is not in the manifest"]
    spec = m[key]
    bad: list[str] = []
    top = _dict(doc)

    def check(section: str, rows: object) -> None:
        bad.extend(
            f"{name} {section}.{k}" for k in sorted(_fields(rows) - set(spec[section]))
        )

    if key == "graph.json":
        for section in ("nodes", "edges", "inbound", "operator"):
            check(section, top.get(section))
        check("health", list(_dict(top.get("health")).values()))
        bad += [
            f"{name} top.{k}"
            for k in sorted(
                set(top)
                - set(spec)
                - {"nodes", "edges", "inbound", "operator", "findings"}
            )
        ]
        bad += [
            f"{name} findings.{r}"
            for r, fs in _dict(top.get("findings")).items()
            if any(
                not isinstance(f, list) or not all(isinstance(x, str) for x in _list(f))
                for f in _list(fs)
            )
        ]
    elif key == "wake.json":
        bad += [f"{name} top.{k}" for k in sorted(set(top) - set(spec["top"]))]
        check("roster", top.get("roster"))
        check(
            "waiting",
            [
                w
                for r in _list(top.get("roster"))
                for w in _list(_dict(r).get("waiting"))
            ],
        )
        bad += [
            f"{name} operator.{k}"
            for k in sorted(set(_dict(top.get("operator"))) - set(spec["operator"]))
        ]
    elif key == "history.json":
        check("weeks", [row for rows in top.values() for row in _list(rows)])
    else:
        check("umbrellas" if key == "umbrellas.json" else "goals", doc)
    return bad
