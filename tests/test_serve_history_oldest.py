# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W853: nemik-serve answers /oldest.json with the rows nemik-history --oldest prints."""

import json
from pathlib import Path

from nemik.check import QUEUE, workstream_files
from nemik.history import oldest_rows
from nemik.serve import DOC_ROUTES, OLDEST_SHOWN, Model

ALPHA: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {
            "symbol": "W1",
            "title": "Old and untouched",
            "status": "ready",
            "issued_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "symbol": "W2",
            "title": "Newer and waiting",
            "status": "blocked",
            "blocked_on": ["W1"],
            "issued_at": "2026-06-01T00:00:00+00:00",
        },
        {
            "symbol": "W3",
            "title": "Finished long ago",
            "status": "done",
            "issued_at": "2025-01-01T00:00:00+00:00",
        },
    ]
}


def _fleet(root: Path) -> None:
    """Write alpha's queue under `root`."""
    state = root / "alpha" / ".claude" / QUEUE
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps(ALPHA), encoding="utf-8")


def test_the_route_is_listed_and_answers_the_commands_rows(tmp_path: Path) -> None:
    """One implementation: the route's rows are oldest_rows over the same queue files."""
    _fleet(tmp_path)
    model = Model(tmp_path)
    model.refresh()
    assert "/oldest.json" in DOC_ROUTES
    want = oldest_rows(dict(workstream_files(tmp_path, QUEUE)), tmp_path, OLDEST_SHOWN)
    assert want, "the fleet has open dated cards"
    assert model.doc_for("/oldest.json") == {"oldest": want}


def test_the_rows_are_open_cards_oldest_first_with_their_flag_and_path(
    tmp_path: Path,
) -> None:
    """The done card is left out, the untouched ready card leads and each row has a path."""
    _fleet(tmp_path)
    rows = oldest_rows(dict(workstream_files(tmp_path, QUEUE)), tmp_path, OLDEST_SHOWN)
    assert [row["cite"] for row in rows] == ["alpha:W1", "alpha:W2"]
    assert [row["flag"] for row in rows] == ["untouched", "stuck"]
    assert all(row["path"] and row["reach"] for row in rows)
