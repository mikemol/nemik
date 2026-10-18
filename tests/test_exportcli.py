# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W635: derived exports give the pod exactly the graph luthen's version-1 list gives."""

import json
from pathlib import Path

from nemik.exportcli import main
from nemik.exportwire import repo_symbols
from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _ids(out: Path) -> list[str]:
    """Read the published graph's node ids and states.

    Args:
        out: A static build's output directory.

    Returns:
        "id state" for each node, in published order.

    """
    doc: object = json.loads((out / "graph.json").read_text())
    found: object = doc.get("nodes") if isinstance(doc, dict) else None
    nodes: list[object] = found if isinstance(found, list) else []
    return [f"{n.get('id')} {n.get('state')}" for n in nodes if isinstance(n, dict)]


def _derive(withheld: Path, out: Path) -> None:
    """Run nemik-exports on the fixture fleet.

    Args:
        withheld: luthen's version-1 list.
        out: Where the exports go.

    """
    main(["--root", str(FLEET), "--withheld", str(withheld), "--out", str(out)])


def test_derived_exports_publish_what_the_v1_list_publishes(tmp_path: Path) -> None:
    """One withheld ref: a build from the derived exports equals a build from the v1 list."""
    repo, symbols = next((r, s) for r, s in repo_symbols(FLEET).items() if s)
    v1: dict[str, object] = {
        "version": 1,
        "as_of": "x",
        "items": [{"ref": f"{repo}:{symbols[0]}", "field": "title", "rule": "r"}],
    }
    withheld = tmp_path / "withheld.json"
    withheld.write_text(json.dumps(v1), encoding="utf-8")
    exports = tmp_path / "exports"
    _derive(withheld, exports)
    build_static(FLEET, tmp_path / "v1", withheld)
    build_static(FLEET, tmp_path / "v2", withheld, exports=exports)
    assert _ids(tmp_path / "v2") == _ids(tmp_path / "v1")


def test_one_export_is_written_per_repo(tmp_path: Path) -> None:
    """Every repo under the root gets its <repo>.json."""
    withheld = tmp_path / "withheld.json"
    doc: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(doc), encoding="utf-8")
    _derive(withheld, tmp_path / "e")
    written = sorted(p.stem for p in (tmp_path / "e").glob("*.json"))
    assert written == sorted(repo_symbols(FLEET))
