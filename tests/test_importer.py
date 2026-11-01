# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W367: the printed import runs cleanly through the real writer and rebuilds the links."""

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import pytest

from nemik.importer import commands
from nemik.projection import Link, Task

WRITER = str(Path(sys.executable).parent / "mikemol-paths-forward")


class _Card(TypedDict, total=False):
    """The fields of a queue card this test reads."""

    symbol: str
    status: str
    blocked_on: list[str]
    caused_by: str


class _Queue(TypedDict):
    """The part of a queue file this test reads."""

    waypoints: list[_Card]


def _tasks() -> list[Task]:
    return [
        Task(1, "x:W1", "design the thing", done=False),
        Task(
            2,
            "x:W2",
            "build the thing",
            done=False,
            preds=(Link("x:W1", cross_repo=False),),
        ),
        Task(
            3,
            "x:W3",
            "ship it",
            done=False,
            preds=(Link("x:W2", cross_repo=False), Link("y:W9", cross_repo=True)),
        ),
        Task(4, "x:W4", "an old step", done=True),
    ]


def _run(cmds: list[list[str]]) -> None:
    for cmd in cmds:
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def _queue(tmp_path: Path) -> Path:
    state = tmp_path / "q.json"
    subprocess.run(
        [WRITER, "--state", str(state), "--init"], check=True, capture_output=True
    )
    _run([[WRITER, "--state", str(state), "--add", "already here"]])  # counter is 1 now
    return state


def test_the_printed_commands_run_and_rebuild_the_links(tmp_path: Path) -> None:
    """The printed commands run and rebuild the links."""
    state = _queue(tmp_path)
    cmds = commands(_tasks(), "mspdi", "plan.xml", state, WRITER)
    assert all(shlex.split(shlex.join(c)) == c for c in cmds)  # survives printing
    _run(cmds)
    doc: _Queue = json.loads(state.read_text())
    cards = {c["symbol"]: c for c in doc["waypoints"]}
    by_source = {c.get("caused_by"): c for c in cards.values()}
    w1, w2, w3, w4 = (by_source[f"mspdi:plan.xml#{u}"] for u in (1, 2, 3, 4))
    assert [w1["symbol"], w2["symbol"], w3["symbol"], w4["symbol"]] == [
        "W2",
        "W3",
        "W4",
        "W5",
    ]
    assert w1["status"] == "ready"
    assert w2["blocked_on"] == ["W2"]
    assert w3["blocked_on"] == ["W3", "y:W9"]  # an outside link keeps its cite
    assert w4["status"] == "done"


def test_a_reimport_prints_nothing_already_imported(tmp_path: Path) -> None:
    """A reimport prints nothing already imported."""
    state = _queue(tmp_path)
    _run(commands(_tasks(), "mspdi", "plan.xml", state, WRITER))
    again = commands(_tasks(), "mspdi", "plan.xml", state, WRITER)
    assert again == []


def test_a_corrupt_queue_is_refused_not_read_as_no_cards(tmp_path: Path) -> None:
    """A queue that is not an object, or whose waypoints is not an array, raises TypeError."""
    state = tmp_path / "q.json"
    state.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="queue object"):
        commands(_tasks(), "mspdi", "plan.xml", state, WRITER)
    state.write_text('{"waypoints": {}}', encoding="utf-8")
    with pytest.raises(TypeError, match="not an array"):
        commands(_tasks(), "mspdi", "plan.xml", state, WRITER)
    state.write_text("null", encoding="utf-8")
    assert commands(_tasks(), "mspdi", "plan.xml", state, WRITER)
