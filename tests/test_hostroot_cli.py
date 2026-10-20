# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W779: nemik-hostroot writes the newest row of each resource, or says why it cannot."""

import json
from pathlib import Path

from nemik.hostroot import read_document
from nemik.hostroot_cli import main

OLD = (
    '{"as_of": "2026-10-20T10:00:00Z", "gate": "", "id": "a", "reading": "r", '
    '"state": "blocked", "waitsFor": ["b"]}'
)
NEW = (
    '{"as_of": "2026-10-20T11:00:00Z", "gate": "", "id": "a", "reading": "r", '
    '"state": "done", "waitsFor": []}'
)


def _luthen(root: Path, body: str) -> None:
    """Put a luthen checkout under `root` whose vlogs_query runs `body`."""
    package = root / "luthen-observability" / "checks"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "vlogs_query.py").write_text(body, encoding="utf-8")


def _record(message: str) -> str:
    """Wrap a document in a record the way VictoriaLogs prints it.

    Returns:
        One line of JSON.

    """
    return '{"_msg": ' + json.dumps(message) + ', "stream": "host_root_frontier"}'


def test_the_newest_row_of_an_id_is_written(tmp_path: Path) -> None:
    """Two refreshes of one id leave one row, the later one."""
    lines = "\n".join([_record(OLD), _record(NEW)])
    _luthen(tmp_path, f"print({lines!r})\n")
    out = tmp_path / "host-root.json"
    assert main(["--root", str(tmp_path), "--out", str(out)]) == 0
    written = out.read_text(encoding="utf-8")
    assert '"state": "done"' in written
    assert '"state": "blocked"' not in written
    assert '"as_of": "2026-10-20T11:00:00Z"' in written


def test_the_document_reads_back_into_its_rows(tmp_path: Path) -> None:
    """What nemik-hostroot writes, read_document returns: the stamp and each row's fields."""
    lines = "\n".join([_record(OLD), _record(NEW)])
    _luthen(tmp_path, f"print({lines!r})\n")
    out = tmp_path / "host-root.json"
    assert main(["--root", str(tmp_path), "--out", str(out)]) == 0
    as_of, rows = read_document(out.read_text(encoding="utf-8"))
    assert as_of.endswith("Z")
    assert [(row.ident, row.state, row.waits_for) for row in rows] == [
        ("a", "done", [])
    ]


def test_a_tool_that_fails_writes_nothing(tmp_path: Path) -> None:
    """A failing query is exit 1 and no file, so a stale document is not refreshed by a bad run."""
    _luthen(tmp_path, "raise SystemExit(2)\n")
    out = tmp_path / "host-root.json"
    assert main(["--root", str(tmp_path), "--out", str(out)]) == 1
    assert not out.exists()


def test_an_answer_with_no_readable_row_writes_nothing(tmp_path: Path) -> None:
    """Garbage lines are skipped; with nothing left, exit 1 and no file."""
    _luthen(tmp_path, 'print("not json")\n')
    out = tmp_path / "host-root.json"
    assert main(["--root", str(tmp_path), "--out", str(out)]) == 1
    assert not out.exists()
