# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W751: nemik-hostroot --landings writes mikemol-commit's landings, or says why not."""

import json
from pathlib import Path

from nemik.hostroot_cli import main
from nemik.landings import read_document, series

GATE_NEMIK = 692
GATE_MTOOLS = 938


def _luthen(root: Path, body: str) -> None:
    """Put a luthen checkout under `root` whose vlogs_query runs `body`."""
    package = root / "luthen-observability" / "checks"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "vlogs_query.py").write_text(body, encoding="utf-8")


def _record(repo: str, sha: str, gate: int, when: str) -> str:
    """Print one landing the way VictoriaLogs does.

    Returns:
        One line of JSON.

    """
    message = {
        "event": "landing",
        "repo": repo,
        "sha": sha,
        "card": "W1",
        "gate_s": str(gate),
    }
    wrapped = json.dumps(json.dumps(message))
    return '{"_msg": ' + wrapped + ', "_time": ' + json.dumps(when) + "}"


def test_the_landings_are_written_oldest_first_and_read_back(tmp_path: Path) -> None:
    """Newest-first lines from the stream come out as a document in landing order."""
    lines = "\n".join(
        [
            _record("mtools", "f39dd23", GATE_MTOOLS, "2026-10-21T05:39:49Z"),
            _record("nemik", "d48dfe1", GATE_NEMIK, "2026-10-21T02:31:49Z"),
        ]
    )
    _luthen(tmp_path, f"print({lines!r})\n")
    out = tmp_path / "landings.json"
    assert main(["--root", str(tmp_path), "--landings", "--out", str(out)]) == 0
    as_of, rows = read_document(out.read_text(encoding="utf-8"))
    assert as_of.endswith("Z")
    assert [row.sha for row in rows] == ["d48dfe1", "f39dd23"]
    assert series(rows) == {"nemik": [GATE_NEMIK], "mtools": [GATE_MTOOLS]}


def test_an_answer_with_no_landing_writes_nothing(tmp_path: Path) -> None:
    """With nothing readable, exit 1 and no file, so a stale document is not refreshed."""
    _luthen(tmp_path, 'print("not json")\n')
    out = tmp_path / "landings.json"
    assert main(["--root", str(tmp_path), "--landings", "--out", str(out)]) == 1
    assert not out.exists()
