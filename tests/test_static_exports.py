# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W634: the static build lets each repo's own export decide what leaves it."""

import json
from pathlib import Path

from nemik.exportwire import repo_symbols
from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _withheld_list(directory: Path) -> Path:
    """Write luthen's version-1 list withholding nothing.

    Args:
        directory: Where to write it.

    Returns:
        The file.

    """
    path = directory / "withheld.json"
    doc: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    path.write_text(json.dumps(doc))
    return path


def _nodes(out: Path) -> list[dict[str, object]]:
    """Read the published graph's nodes.

    Args:
        out: The static build's output directory.

    Returns:
        The nodes of graph.json.

    """
    doc: object = json.loads((out / "graph.json").read_text())
    found: object = doc.get("nodes") if isinstance(doc, dict) else None
    items: list[object] = found if isinstance(found, list) else []
    return [{str(k): v for k, v in n.items()} for n in items if isinstance(n, dict)]


def test_no_exports_publishes_no_card(tmp_path: Path) -> None:
    """An empty exports directory: every card of every repo is withheld, so none is published."""
    exports = tmp_path / "exports"
    exports.mkdir()
    out = tmp_path / "out"
    build_static(FLEET, out, _withheld_list(tmp_path), exports=exports)
    published = [
        n for n in _nodes(out) if n.get("repo") and n.get("state") != "withheld"
    ]
    assert published == []


def test_exports_that_publish_every_card_equal_a_build_without_exports(
    tmp_path: Path,
) -> None:
    """Each repo's export publishing all its cards gives the same graph as no exports at all."""
    exports = tmp_path / "exports"
    exports.mkdir()
    for repo, symbols in repo_symbols(FLEET).items():
        export = {
            "version": 2,
            "repo": repo,
            "cards": [{"symbol": s} for s in symbols],
            "withheld": [],
        }
        (exports / f"{repo}.json").write_text(json.dumps(export))
    plain = tmp_path / "plain"
    gated = tmp_path / "gated"
    build_static(FLEET, plain, _withheld_list(tmp_path))
    build_static(FLEET, gated, _withheld_list(tmp_path), exports=exports)
    assert _nodes(gated) == _nodes(plain)
