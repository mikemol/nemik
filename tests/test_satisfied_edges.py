"""nemik:W56: edges from done work are marked satisfied; open_blockers counts the rest."""

import json
from pathlib import Path

from nemik.serve import Model


def test_done_children_satisfy_their_edges(tmp_path: Path) -> None:
    d = tmp_path / "a" / ".claude"
    d.mkdir(parents=True)
    wps = [
        {"symbol": "W1", "title": "parent", "status": "blocked", "enables": [],
         "blocked_on": ["W2", "W3"], "blocked_kind": "agent"},
        {"symbol": "W2", "title": "done child", "status": "done", "enables": ["W1"]},
        {"symbol": "W3", "title": "open child", "status": "ready", "enables": ["W1"]},
    ]
    (d / "paths-forward.json").write_text(json.dumps(
        {"version": 1, "project_root": "/x", "counter": 3, "waypoints": wps, "residue": []}))
    m = Model(tmp_path)
    m.refresh()
    out = json.loads(m.payload)
    edges = {(e["source"].rsplit("/", 1)[-1], e["target"].rsplit("/", 1)[-1], e["kind"]): e["satisfied"]
             for e in out["edges"]}
    assert edges[("W2", "W1", "enables")] is True
    assert edges[("W3", "W1", "enables")] is False
    parent = next(n for n in out["nodes"] if n["symbol"] == "W1")
    assert edges[("W1", "W2", "waits")] is True
    assert edges[("W1", "W3", "waits")] is False
    assert parent["open_blockers"] == 1  # W3 only, counted once across both edge kinds
