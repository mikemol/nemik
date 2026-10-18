# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W636: the pod's --publish build takes the repos' exports and rebuilds when one changes."""

import json
from pathlib import Path

from nemik.serve import publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _states(snap: Path) -> set[str]:
    """Read the states of the published graph's nodes.

    Args:
        snap: A published snapshot directory.

    Returns:
        The set of node states, as strings.

    """
    doc: object = json.loads((snap / "graph.json").read_text())
    found: object = doc.get("nodes") if isinstance(doc, dict) else None
    nodes: list[object] = found if isinstance(found, list) else []
    return {str(n.get("state")) for n in nodes if isinstance(n, dict) and n.get("repo")}


def test_a_publish_with_empty_exports_releases_no_card(tmp_path: Path) -> None:
    """No export for any repo: every repo node in the snapshot is a withheld stub."""
    exports = tmp_path / "exports"
    exports.mkdir()
    snap = publish(FLEET, tmp_path / "pod", None, exports=exports)
    assert snap is not None
    assert _states(snap) <= {"withheld"}


def test_a_publish_without_exports_is_unchanged(tmp_path: Path) -> None:
    """Without --exports the private build withholds nothing, as before."""
    snap = publish(FLEET, tmp_path / "pod", None)
    assert snap is not None
    assert _states(snap) - {"withheld"}


def test_a_changed_export_rebuilds_the_snapshot(tmp_path: Path) -> None:
    """Same queues, a new export file: the second publish builds again instead of 'unchanged'."""
    exports = tmp_path / "exports"
    exports.mkdir()
    base = tmp_path / "pod"
    assert publish(FLEET, base, None, exports=exports) is not None
    assert publish(FLEET, base, None, exports=exports) is None
    (exports / "nemik.json").write_text("{}", encoding="utf-8")
    assert publish(FLEET, base, None, exports=exports) is not None
