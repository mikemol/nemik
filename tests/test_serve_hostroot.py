# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W780: nemik-serve shows the host-root frontier from nemik-hostroot's file."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nemik.serve import Model

STAMP = "%Y-%m-%dT%H:%M:%SZ"


def _document(as_of: str, row_as_of: str) -> str:
    """Write the text nemik-hostroot writes: the stamp first, one row per line.

    Returns:
        The document.

    """
    row = (
        '{"id": "local_file.host[\\"x\\"]", "state": "blocked", "waitsFor": ["y"], '
        f'"gate": "observable", "reading": "root-only", "as_of": "{row_as_of}"}}'
    )
    return f'{{"as_of": "{as_of}", "rows": [\n  {row}\n]}}\n'


def _stamp(hours_ago: float) -> str:
    """Make a stamp.

    Returns:
        An ISO stamp that many hours before now.

    """
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime(STAMP)


def _model(root: Path, path: Path | None) -> Model:
    """Make a model that was given the host-root file, as main does.

    Returns:
        The model.

    """
    model = Model(root)
    model.hostroot = path
    return model


def test_no_file_configured_serves_no_board(tmp_path: Path) -> None:
    """Without --hostroot the board is off and says why."""
    doc = _model(tmp_path, None).hostroot_doc()
    assert doc == {"host": False, "why": "no --hostroot file"}


def test_a_missing_file_serves_no_board_and_no_path(tmp_path: Path) -> None:
    """A file that is not there is 'no document', never the host path."""
    doc = _model(tmp_path, tmp_path / "gone.json").hostroot_doc()
    assert doc == {"host": False, "why": "no document"}


def test_a_fresh_document_serves_its_rows(tmp_path: Path) -> None:
    """The row's fields come across, with the escaped id intact and nothing stale."""
    path = tmp_path / "host-root.json"
    seen = _stamp(0.2)
    path.write_text(_document(_stamp(0.1), seen), encoding="utf-8")
    doc = _model(tmp_path, path).hostroot_doc()
    assert doc["host"] is True
    assert doc["stale"] is False
    assert doc["rows"] == [
        {
            "id": 'local_file.host["x"]',
            "state": "blocked",
            "waitsFor": ["y"],
            "gate": "observable",
            "reading": "root-only",
            "as_of": seen,
            "stale": False,
        }
    ]


def test_an_old_document_is_marked_stale(tmp_path: Path) -> None:
    """Past two hours the document is stale."""
    path = tmp_path / "host-root.json"
    path.write_text(_document(_stamp(5), _stamp(6)), encoding="utf-8")
    assert _model(tmp_path, path).hostroot_doc()["stale"] is True


def test_an_unreadable_document_serves_no_board(tmp_path: Path) -> None:
    """A document with no stamp on its first line says so instead of showing nothing."""
    path = tmp_path / "host-root.json"
    path.write_text("[]\n", encoding="utf-8")
    doc = _model(tmp_path, path).hostroot_doc()
    assert doc == {"host": False, "why": "no as_of on the first line"}
