# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W670: nemik-serve --series serves luthen's snapshot as a board, and none when it cannot."""

import json
import time
from pathlib import Path

from nemik.apischema import unmanifested
from nemik.serve import SERIES_FILE, Model, static_data

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_published_wake_document_carries_the_board(tmp_path: Path) -> None:
    """A snapshot beside the queues becomes wake.json's series, and the manifest knows the field."""
    snap = _snapshot(tmp_path / SERIES_FILE)
    wake = static_data(Model(FLEET, series=snap))["wake.json"]
    assert unmanifested("wake.json", wake) == []
    shown = json.dumps(wake)
    assert '"series": {"board": true' in shown
    assert '"state": "asleep"' in shown
    none = json.dumps(static_data(Model(FLEET))["wake.json"])
    assert '"series": {"board": false, "why": "no --series file"' in none


def test_a_withheld_card_is_not_counted_as_work(tmp_path: Path) -> None:
    """The withheld list keeps a card out of every number the view publishes, the board's too."""
    model = _model(tmp_path, _snapshot(tmp_path / "s.json"))
    model.withheld = frozenset({"slow:W1"})
    nodes: list[dict[str, str]] = [
        {"repo": "slow", "symbol": "W1", "state": "ready"},
        {"repo": "up", "symbol": "W2", "state": "ready"},
    ]
    doc: dict[str, object] = {"operator": [], "inbound": [], "nodes": nodes}
    model.doc = doc
    board = model.series_doc()
    assert board["stranded"] == []
    assert '"ready": 0' in json.dumps(board["repos"])


def _snapshot(path: Path, age: int = 30) -> Path:
    """Write a snapshot in the agreed shape, as luthen wrote it `age` seconds ago.

    Args:
        path: Where to write it.
        age: Seconds since luthen wrote it.

    Returns:
        The path.

    """
    now = int(time.time())
    body = {
        "version": 1,
        "as_of": now - age,
        "liveness": {
            "up": {
                "verdict": "ok",
                "last_tick": now - 60,
                "history": [[now - 60, "ok"]],
            },
            "gone": {"verdict": "dormant", "history": [[now - 600, "dormant"]]},
            "slow": {"verdict": "stale", "history": []},
        },
        "tokens": [],
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _model(tmp_path: Path, series: Path | None, max_age: int = 900) -> Model:
    """Make a model whose queue holds ready cards in three repos.

    Args:
        tmp_path: A scratch directory, the model's root.
        series: The snapshot file, or None.
        max_age: The oldest snapshot accepted, in seconds.

    Returns:
        The model, with its document set.

    """
    model = Model(tmp_path, series=series, series_max_age=max_age)
    nodes = [
        {"repo": "up", "state": "ready"},
        {"repo": "gone", "state": "working"},
        {"repo": "gone", "state": "done"},
        {"repo": "slow", "state": "ready"},
    ]
    operator: list[object] = []
    inbound: list[object] = []
    doc: dict[str, object] = {
        "operator": operator,
        "inbound": inbound,
        "nodes": nodes,
    }
    model.doc = doc
    return model


def test_no_series_file_serves_no_board(tmp_path: Path) -> None:
    """Without --series there is nothing to draw, and the reply says so."""
    doc = _model(tmp_path, None).series_doc()
    assert doc["board"] is False
    assert "series" in str(doc["why"])


def test_a_fresh_snapshot_becomes_a_board(tmp_path: Path) -> None:
    """Each repo has its state and ready count; the asleep and idle repos with work are stranded."""
    doc = _model(tmp_path, _snapshot(tmp_path / "s.json")).series_doc()
    assert doc["board"] is True
    assert doc["stranded"] == ["gone", "slow"]
    repos = json.dumps(doc["repos"])
    assert '"state": "awake"' in repos
    assert '"state": "asleep"' in repos
    assert '"ready": 1' in repos


def test_a_stale_snapshot_serves_no_board(tmp_path: Path) -> None:
    """A producer that stopped must not read as a live board."""
    old = _snapshot(tmp_path / "s.json", age=2000)
    doc = _model(tmp_path, old).series_doc()
    assert doc["board"] is False
    assert "as_of" in str(doc["why"])


def test_a_missing_file_serves_no_board(tmp_path: Path) -> None:
    """A file the egress gate removed is 'not ruled', so no board, not an empty one."""
    doc = _model(tmp_path, tmp_path / "gone.json").series_doc()
    assert doc["board"] is False
