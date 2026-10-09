"""nemik:W172: luthen's withheld list applied to the static view's documents, failing closed.

Contract (luthen-observability-6b, 2026-10-01; nemik:W153 evidence): WITHHOLD WHOLE, NEVER SCRUB.
The file is required; a missing one means the gate did not run, so the build fails. Shape v1:
{"version": 1, "as_of": ..., "items": [{"ref": "repo:W<n>", "field": ..., "rule": ...}]}; refs are
a set, `field`/`rule` are for the owning repo and ignored here; `items: []` withholds nothing.

A withheld item publishes nothing of its own: no title, ask, blockers, effort or goal entry. Where
a published item points at it, the end is a stub carrying the symbol only, so no dependency
silently disappears (luthen confirmed this reading 2026-10-01: "no edges into it" meant no node or
content, not losing the dependency). An edge between two withheld items is dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nemik.adapter import BASE


class WithheldError(ValueError):
    """The withheld list is missing or unreadable: never publish ungated."""


def load(path: Path | None) -> frozenset[str]:
    if path is None or not path.exists():
        raise WithheldError(
            f"withheld list {path} is missing: the gate did not run, refusing to publish"
        )
    try:
        doc = json.loads(path.read_text())
    except ValueError as e:
        raise WithheldError(f"withheld list {path} is not JSON: {e}") from e
    if doc.get("version") != 1:
        raise WithheldError(
            f"withheld list {path}: unknown version {doc.get('version')!r}"
        )
    items = doc.get("items")
    if not isinstance(items, list) or not all(
        isinstance(i, dict) and isinstance(i.get("ref"), str) for i in items
    ):
        raise WithheldError(
            f"withheld list {path}: items must be a list of {{ref, field, rule}}"
        )
    return frozenset(i["ref"] for i in items)


def _id(ref: str) -> str:
    return f"{BASE}{ref.replace(':', '/', 1)}"


def _stub(ref: str) -> dict:
    repo, _, sym = ref.partition(":")
    return {
        "id": _id(ref),
        "repo": repo,
        "symbol": sym,
        "cite": ref,
        "state": "withheld",
        "title": "withheld",
        "blocked_on": [],
        "blocked_kind": "",
        "caused_by": "",
        "minted_during": "",
        "effort": {},
        "last_activity": "",
        "open_blockers": 0,
        "weather": "",
    }


def apply(docs: dict[str, Any], refs: frozenset[str]) -> dict[str, Any]:
    """The documents with every withheld item dropped whole (stubs where a published item points)."""
    if not refs:
        return docs
    ids = {_id(r) for r in refs}
    out = dict(docs)
    g = dict(docs["graph.json"])
    nodes = [n for n in g["nodes"] if n["id"] not in ids and n.get("for") not in refs]
    edges = [e for e in g["edges"] if not (e["source"] in ids and e["target"] in ids)]
    pointed = {end for e in edges for end in (e["source"], e["target"]) if end in ids}
    nodes += [_stub(r) for r in sorted(refs) if _id(r) in pointed]
    g["nodes"] = sorted(nodes, key=lambda n: n["id"])
    g["edges"] = edges
    g["inbound"] = [b for b in g["inbound"] if b["blocked"] not in refs]
    g["operator"] = [a for a in g["operator"] if a["ref"] not in refs]
    out["graph.json"] = g
    wake = dict(docs["wake.json"])
    hide = lambda rows: [
        w if w["blocked"] not in refs else {**w, "title": "withheld"} for w in rows
    ]
    wake["roster"] = [{**r, "waiting": hide(r["waiting"])} for r in wake["roster"]]
    wake["operator"] = {
        **wake["operator"],
        "waiting": [w for w in wake["operator"]["waiting"] if w["blocked"] not in refs],
    }
    out["wake.json"] = wake
    for name, doc in docs.items():
        if name.startswith("goals/"):
            repo = name.removeprefix("goals/").removesuffix(".json")
            # A goals entry carries its frontier leaves' blocked_on text in `outside` (nemik.rank
            # .frontier), so it holds withheld content whenever a leaf is withheld, not only when
            # the goal is (luthen-observability found aeternum:W74's text under W75-W77, 2026-10-02).
            # The entry is dropped whole, never scrubbed.
            out[name] = [
                r
                for r in doc
                if f"{repo}:{r['goal']}" not in refs
                and not refs & set(r["frontier"])
                and r.get("on_deck") not in refs
            ]
    return out
