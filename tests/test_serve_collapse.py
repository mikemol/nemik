# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W864: nemik-serve answers /collapse.json with the lines nemik-collapse prints."""

import json
from pathlib import Path

from nemik.check import blocked_rows
from nemik.collapse import lines
from nemik.serve import DOC_ROUTES, Model

QUEUE: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W1", "title": "umbrella", "status": "ready"},
        {"symbol": "W2", "title": "waits", "status": "blocked", "blocked_on": ["W1"]},
        {
            "symbol": "W3",
            "title": "also waits",
            "status": "blocked",
            "blocked_on": ["W1"],
        },
    ]
}


def test_the_route_is_listed_and_answers_the_commands_lines(tmp_path: Path) -> None:
    """One implementation: the route's lines are collapse.lines over the same graph's rows."""
    state = tmp_path / "alpha" / ".claude" / "paths-forward.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps(QUEUE), encoding="utf-8")
    model = Model(tmp_path)
    model.refresh()
    assert "/collapse.json" in DOC_ROUTES
    want = lines(blocked_rows(model.graph))
    assert want, "two cards waiting on one give the command something to print"
    assert model.doc_for("/collapse.json") == {"lines": want}
