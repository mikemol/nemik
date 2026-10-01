"""nemik:W154: the field manifest for the static public view.

`data/field-manifest.json` names every field each published file may carry. `unmanifested` returns
the fields a rendered document has that the manifest does not, so the static build (nemik:W153)
fails instead of publishing a field nobody classified (operator 2026-10-01, luthen's withhold-whole
contract). It checks the export's shape, not its values: which items are withheld is luthen's list.
"""

from __future__ import annotations

import json
from importlib.resources import files


def load() -> dict:
    return json.loads(files("nemik.data").joinpath("field-manifest.json").read_text())["files"]


def _fields(rows) -> set[str]:
    return {k for r in rows for k in r} if isinstance(rows, list) else set()


def unmanifested(name: str, doc) -> list[str]:
    """`path.field` for every field of `doc` (the parsed published file `name`) not in the manifest."""
    m = load()
    key = "goals/<repo>.json" if name.startswith("goals/") else name
    if key not in m:
        return [f"{name}: file is not in the manifest"]
    spec, bad = m[key], []

    def check(section: str, rows) -> None:
        bad.extend(f"{name} {section}.{k}" for k in sorted(_fields(rows) - set(spec[section])))

    if key == "graph.json":
        for section in ("nodes", "edges", "inbound", "operator"):
            check(section, doc.get(section))
        bad += [f"{name} top.{k}" for k in sorted(set(doc) - set(spec) - {"nodes", "edges", "inbound", "operator", "findings"})]
        bad += [f"{name} findings.{r}" for r, fs in doc.get("findings", {}).items()
                if any(not isinstance(f, list) or not all(isinstance(x, str) for x in f) for f in fs)]
    elif key == "wake.json":
        bad += [f"{name} top.{k}" for k in sorted(set(doc) - set(spec["top"]))]
        check("roster", doc.get("roster"))
        check("waiting", [w for r in doc.get("roster", []) for w in r.get("waiting", [])])
        bad += [f"{name} operator.{k}" for k in sorted(set(doc.get("operator", {})) - set(spec["operator"]))]
    else:
        check("goals", doc)
    return bad
