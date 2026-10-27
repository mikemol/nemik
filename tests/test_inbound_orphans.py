# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W376: nemik-inbound REPO lists REPO's uncited inbox letters as UNCLAIMED rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nemik.blocks_cli import main
from nemik.letters import _today


def _repo(root: Path, cites: str = "") -> None:
    queue = root / "a" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    card: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "ready",
        "next_bounded_step": "x",
        "evidence": cites,
    }
    body: dict[str, object] = {
        "version": 1,
        "project_root": "/x",
        "counter": 1,
        "residue": [],
        "waypoints": [card],
    }
    queue.write_text(json.dumps(body))
    inbox = root / "a" / "inbox"
    inbox.mkdir()
    name = f"{_today().isoformat()}-b-please-do-x.md"
    (inbox / name).write_text("From: b (W9)\nTo: a\n\nplease do x\n")


def test_an_uncited_letter_is_an_unclaimed_row_with_its_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    main(["a", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "<- letter" in out
    assert "UNCLAIMED" in out
    assert "--add" in out
    assert "--caused-by inbox/" in out


def test_a_cited_letter_is_not_listed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    name = f"{_today().isoformat()}-b-please-do-x.md"
    _repo(tmp_path, cites=f"a/inbox/{name}")
    main(["a", "--root", str(tmp_path)])
    assert "<- letter" not in capsys.readouterr().out
