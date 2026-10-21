# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W751: nemik-serve shows the commit landings from nemik-hostroot --landings' file."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nemik.landings import Landing, document
from nemik.serve import Model

STAMP = "%Y-%m-%dT%H:%M:%SZ"
ROWS = [
    Landing("nemik", "d48dfe1", "W827", 692, "2026-10-21T02:31:49Z"),
    Landing("mtools", "f39dd23", "W1651", 938, "2026-10-21T05:39:49Z"),
    Landing("nemik", "bb9ba08", "W829", 487, "2026-10-21T04:28:48Z"),
]
GATES = {"nemik": [692, 487], "mtools": [938]}
SHOWN = [
    {
        "repo": row.repo,
        "sha": row.sha,
        "card": row.card,
        "gate_s": row.gate_s,
        "when": row.when,
    }
    for row in ROWS
]


def _stamp(hours_ago: float) -> str:
    """Make a stamp.

    Returns:
        An ISO stamp that many hours before now.

    """
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime(STAMP)


def _model(root: Path, path: Path | None) -> Model:
    """Make a model that was given the landings file, as main does.

    Returns:
        The model.

    """
    model = Model(root)
    model.landings = path
    return model


def test_no_file_configured_serves_no_board(tmp_path: Path) -> None:
    """Without --landings the board is off and says why."""
    doc = _model(tmp_path, None).landings_doc()
    assert doc == {"host": False, "why": "no --landings file"}


def test_a_missing_file_serves_no_board_and_no_path(tmp_path: Path) -> None:
    """A file that is not there is 'no document', never the host path."""
    doc = _model(tmp_path, tmp_path / "gone.json").landings_doc()
    assert doc == {"host": False, "why": "no document"}


def test_a_fresh_document_serves_its_landings_and_series(tmp_path: Path) -> None:
    """Each repo's gate seconds come across in landing order, and nothing is stale."""
    path = tmp_path / "landings.json"
    path.write_text(document(ROWS, _stamp(0.1)), encoding="utf-8")
    doc = _model(tmp_path, path).landings_doc()
    assert doc["host"] is True
    assert doc["stale"] is False
    assert doc["series"] == GATES
    assert doc["landings"] == SHOWN


def test_an_old_document_is_marked_stale(tmp_path: Path) -> None:
    """Past two hours the document is stale."""
    path = tmp_path / "landings.json"
    path.write_text(document(ROWS, _stamp(5)), encoding="utf-8")
    assert _model(tmp_path, path).landings_doc()["stale"] is True


def test_the_route_answers_for_both_host_boards(tmp_path: Path) -> None:
    """host_board picks the landings board for its route and the host-root board for the other."""
    path = tmp_path / "landings.json"
    path.write_text(document(ROWS, _stamp(0.1)), encoding="utf-8")
    model = _model(tmp_path, path)
    assert model.host_board("/landings.json") == model.landings_doc()
    assert model.host_board("/hostroot.json") == model.hostroot_doc()
