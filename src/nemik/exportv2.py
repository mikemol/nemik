# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W634: a repo's own export decides what leaves it, and fails closed per repo.

Shape v2 (docs/withholding-at-source.md):
{"version": 2, "repo": ..., "cards": [{"symbol": ...}], "withheld": ["repo:W<n>", ...]}.
"""

import json
from pathlib import Path

VERSION = 2


def _fields(path: Path) -> dict[str, object]:
    """Read an export's top-level object.

    Args:
        path: The export file.

    Returns:
        Its fields; empty when the file is missing, not JSON or not an object.

    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        doc: object = json.loads(text)
    except ValueError:
        return {}
    out: dict[str, object] = {}
    if isinstance(doc, dict):
        for key, value in doc.items():
            out[str(key)] = value
    return out


def _symbols(cards: object) -> list[str]:
    """Read the card symbols an export publishes.

    Args:
        cards: The export's `cards` field.

    Returns:
        The symbols; empty when the field is not a list of objects naming one.

    """
    out: list[str] = []
    if not isinstance(cards, list):
        return out
    for card in cards:
        if not isinstance(card, dict):
            return []
        symbol: object = card.get("symbol")
        if not isinstance(symbol, str):
            return []
        out.append(symbol)
    return out


def export_refs(repo: str, symbols: list[str], path: Path) -> set[str]:
    """List the refs of `repo` that must not be published, by the repo's own export.

    Fail closed per repo: an export that is missing, not JSON, of another version or another repo
    withholds every card of the repo, so nothing leaves ungated.

    Args:
        repo: The repo the export belongs to.
        symbols: Every card symbol the repo's queue holds.
        path: The repo's export file.

    Returns:
        The refs to withhold: the export's own, and every card the export does not publish.

    """
    everything = {f"{repo}:{s}" for s in symbols}
    fields = _fields(path)
    named = fields.get("withheld")
    if fields.get("version") != VERSION or fields.get("repo") != repo:
        return everything
    if not isinstance(named, list):
        return everything
    published = {f"{repo}:{s}" for s in _symbols(fields.get("cards"))}
    return (everything - published) | {str(r) for r in named}
