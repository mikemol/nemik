# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
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
from typing import TYPE_CHECKING

from nemik.adapter import BASE

if TYPE_CHECKING:
    from pathlib import Path


class WithheldError(ValueError):
    """The withheld list is missing or unreadable: never publish ungated."""


def _ref(item: object) -> str:
    """Give an item's ref, or an empty string when the item is not an object with a string ref.

    Returns:
        The ref, or "".

    """
    if isinstance(item, dict):
        ref = item.get("ref")
        if isinstance(ref, str):
            return ref
    return ""


def _list(value: object) -> list[object]:
    """Read a parsed JSON value as an array, or an empty one when it is anything else.

    Returns:
        The array's elements.

    """
    if isinstance(value, list):
        items: list[object] = value
        return items
    return []


def load(path: Path | None) -> frozenset[str]:
    """Read the withheld list the gate wrote.

    Returns:
        The refs it withholds.

    Raises:
        WithheldError: the list is missing, is not JSON, is not an object, has an unknown
            version or has items that are not refs.

    """
    if path is None or not path.exists():
        msg = f"withheld list {path} is missing: the gate did not run, refusing to publish"
        raise WithheldError(msg)
    try:
        doc: object = json.loads(path.read_text())
    except ValueError as e:
        msg = f"withheld list {path} is not JSON: {e}"
        raise WithheldError(msg) from e
    if not isinstance(doc, dict):
        msg = f"withheld list {path}: expected an object, got {type(doc).__name__}"
        raise WithheldError(msg)
    top: dict[str, object] = {str(k): v for k, v in doc.items()}
    if top.get("version") != 1:
        msg = f"withheld list {path}: unknown version {top.get('version')!r}"
        raise WithheldError(msg)
    items = top.get("items")
    refs = [_ref(i) for i in _list(items)]
    if not isinstance(items, list) or not all(refs):
        msg = f"withheld list {path}: items must be a list of {{ref, field, rule}}"
        raise WithheldError(msg)
    return frozenset(refs)


def _id(ref: str) -> str:
    return f"{BASE}{ref.replace(':', '/', 1)}"


def _stub(ref: str) -> dict[str, object]:
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
        "last_worked": "",
        "issued": "",
        "stage": "",
        "open_blockers": 0,
        "weather": "",
    }


def _set(base: dict[str, object], key: str, value: object) -> dict[str, object]:
    """Copy a dict with one key set, as `{**base, key: value}` does (Codon cannot parse that).

    Returns:
        A new dict; `base` is not changed.

    """
    out = dict(base)
    out[key] = value
    return out


def _s(value: object) -> str:
    return value if isinstance(value, str) else ""


def _obj(value: object) -> dict[str, object]:
    """Read a document as an object, refusing anything else: this decides what is published.

    Returns:
        The object's entries, keyed by string.

    Raises:
        TypeError: when the value is not an object.

    """
    if not isinstance(value, dict):
        msg = f"expected an object, got {type(value).__name__}"
        raise TypeError(msg)
    return {str(k): v for k, v in value.items()}


def _rows(value: object) -> list[dict[str, object]]:
    """Read a document part as an array of objects, refusing anything else.

    Returns:
        One entry map per element.

    Raises:
        TypeError: when the value is not an array.

    """
    if not isinstance(value, list):
        msg = f"expected an array, got {type(value).__name__}"
        raise TypeError(msg)
    return [_obj(v) for v in value]


def _node_id(node: dict[str, object]) -> str:
    return _s(node["id"])


def apply(docs: dict[str, object], refs: frozenset[str]) -> dict[str, object]:
    """Drop every withheld item whole from the documents (stubs where a published item points).

    Returns:
        The documents without the withheld items, with a stub where a published item points.

    """
    if not refs:
        return docs
    ids = {_id(r) for r in refs}
    out = dict(docs)
    g = _obj(docs["graph.json"])
    nodes = [
        n
        for n in _rows(g["nodes"])
        if _s(n["id"]) not in ids and _s(n.get("for")) not in refs
    ]
    edges = [
        e
        for e in _rows(g["edges"])
        if not (_s(e["source"]) in ids and _s(e["target"]) in ids)
    ]
    pointed = {
        end for e in edges for end in (_s(e["source"]), _s(e["target"])) if end in ids
    }
    nodes += [_stub(r) for r in sorted(refs) if _id(r) in pointed]
    g["nodes"] = sorted(nodes, key=_node_id)
    g["edges"] = edges
    g["inbound"] = [b for b in _rows(g["inbound"]) if _s(b["blocked"]) not in refs]
    g["operator"] = [a for a in _rows(g["operator"]) if _s(a["ref"]) not in refs]
    out["graph.json"] = g
    wake = _obj(docs["wake.json"])

    def hide(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            w if _s(w["blocked"]) not in refs else _set(w, "title", "withheld")
            for w in rows
        ]

    wake["roster"] = [
        _set(r, "waiting", hide(_rows(r["waiting"]))) for r in _rows(wake["roster"])
    ]
    asks = _obj(wake["operator"])
    wake["operator"] = _set(
        asks,
        "waiting",
        [w for w in _rows(asks["waiting"]) if _s(w["blocked"]) not in refs],
    )
    out["wake.json"] = wake
    for name, doc in docs.items():
        if name.startswith("goals/"):
            repo = name.removeprefix("goals/").removesuffix(".json")
            # A goals entry carries its frontier leaves' blocked_on text in `outside` (nemik.rank
            # .frontier), so it holds withheld content whenever a leaf is withheld, not only when
            # the goal is (luthen-observability found aeternum:W74's text under W75-W77,
            # 2026-10-02). The entry is dropped whole, never scrubbed.
            out[name] = [
                r
                for r in _rows(doc)
                if f"{repo}:{_s(r['goal'])}" not in refs
                and not refs & {_s(x) for x in _list(r["frontier"])}
                and _s(r.get("on_deck")) not in refs
            ]
    return out
