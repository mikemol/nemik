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


def _fields(rows: object) -> set[str]:
    return {k for r in rows for k in r} if isinstance(rows, list) else set()


def unmanifested(name: str, doc, m: Manifest) -> list[str]:
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

    def check(section: str, rows: object) -> None:
        bad.extend(
            f"{name} {section}.{k}" for k in sorted(_fields(rows) - set(spec[section]))
        )

    if key == "graph.json":
        for section in ("nodes", "edges", "inbound", "operator"):
            check(section, doc.get(section))
        check("health", list(doc.get("health", {}).values()))
        bad += [
            f"{name} top.{k}"
            for k in sorted(
                set(doc)
                - set(spec)
                - {"nodes", "edges", "inbound", "operator", "findings"}
            )
        ]
        bad += [
            f"{name} findings.{r}"
            for r, fs in doc.get("findings", {}).items()
            if any(
                not isinstance(f, list) or not all(isinstance(x, str) for x in f)
                for f in fs
            )
        ]
    elif key == "wake.json":
        bad += [f"{name} top.{k}" for k in sorted(set(doc) - set(spec["top"]))]
        check("roster", doc.get("roster"))
        check(
            "waiting", [w for r in doc.get("roster", []) for w in r.get("waiting", [])]
        )
        bad += [
            f"{name} operator.{k}"
            for k in sorted(set(doc.get("operator", {})) - set(spec["operator"]))
        ]
    elif key == "history.json":
        check("weeks", [row for rows in doc.values() for row in rows])
    else:
        check("umbrellas" if key == "umbrellas.json" else "goals", doc)
    return bad
