# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W367: the printed import runs cleanly through the real writer and rebuilds the links."""

import json
import shlex
import subprocess
import sys
from pathlib import Path

from nemik.importer import commands
from nemik.projection import Link, Task

WRITER = str(Path(sys.executable).parent / "mikemol-paths-forward")


def _tasks() -> list[Task]:
    return [
        Task(1, "x:W1", "design the thing", False),
        Task(2, "x:W2", "build the thing", False, (Link("x:W1", False),)),
        Task(3, "x:W3", "ship it", False, (Link("x:W2", False), Link("y:W9", True))),
        Task(4, "x:W4", "an old step", True),
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
    cards = {c["symbol"]: c for c in json.loads(state.read_text())["waypoints"]}
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
