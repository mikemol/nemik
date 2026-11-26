# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1522: the differential harness reads equal, drift and unstable, and freezes its inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from diff_harness import (
    DRIFT,
    EQUAL,
    UNSTABLE,
    differences,
    main,
    masked,
    snapshot,
    verdict,
)

from nemik import queuefiles

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

HOURS = [r"\d+ h", r"\d+\.\d d"]


def test_a_masked_field_compares_equal_and_the_rest_does_not() -> None:
    """The proven masks hide the clock fields only."""
    assert masked("waited 3 h and 1.5 d", HOURS) == "waited <masked> and <masked>"
    assert masked("42 cards", HOURS) == "42 cards"


def test_the_first_differing_lines_are_named() -> None:
    """A line one side lacks counts as empty, and the list stops at the limit."""
    assert differences("a\nb\nc", "a\nb\nc") == []
    assert differences("a\nb", "a\nx\nz") == ["line 2: b | x", "line 3:  | z"]
    assert len(differences("1\n2\n3\n4", "a\nb\nc\nd", limit=2)) == len(("1", "2"))


def test_equal_drift_and_unstable_are_told_apart() -> None:
    """The control (old, old) decides whether the comparison means anything."""
    assert verdict("x\n", "x\n", "x\n", []) == (EQUAL, [])
    assert verdict("x\n", "y\n", "x\n", []) == (DRIFT, ["line 1: x | y"])
    state, moved = verdict("x\n", "x\n", "z\n", [])
    assert state == UNSTABLE
    assert moved == ["line 1: x | z"]


def test_a_masked_clock_is_not_drift_and_not_instability() -> None:
    """Old and new that differ only in a masked field are equal."""
    assert verdict("5 h\n", "7 h\n", "9 h\n", HOURS) == (EQUAL, [])
    assert verdict("5 h\n", "7 d\n", "9 h\n", HOURS)[0] == DRIFT


def _root(base: Path) -> Path:
    # a fleet root with one repo's queue and ledger
    claude = base / "root" / "a" / ".claude"
    claude.mkdir(parents=True)
    (claude / queuefiles.QUEUE).write_text('{"waypoints": []}', encoding="utf-8")
    (claude / queuefiles.LEDGER).write_text("", encoding="utf-8")
    return base / "root"


def test_the_snapshot_copies_each_repos_queue_and_ledger_once(tmp_path: Path) -> None:
    """Both files of the repo land under the scratch root, and nothing else does."""
    root = _root(tmp_path)
    scratch = tmp_path / "frozen"
    assert snapshot(root, scratch) == len(("queue", "ledger"))
    files = (p for p in scratch.rglob("*") if p.is_file())
    held = sorted(p.relative_to(scratch).as_posix() for p in files)
    assert held == sorted(
        [f"a/.claude/{queuefiles.LEDGER}", f"a/.claude/{queuefiles.QUEUE}"]
    )


def _tree(base: Path, name: str, body: str) -> Path:
    # a source tree whose module `probe` prints `body` and the number of queue files in <root>
    src = base / name / "src"
    src.mkdir(parents=True)
    (src / "probe.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        f"print({body!r})\n"
        "print(len(list(Path(sys.argv[1]).rglob('*.json'))))\n",
        encoding="utf-8",
    )
    return base / name


def test_old_new_old_over_two_trees_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same output is equal (exit 0); a planted change is drift (exit 1) naming the line."""
    root = _root(tmp_path)
    old = _tree(tmp_path, "old", "same")
    same = _tree(tmp_path, "same", "same")
    other = _tree(tmp_path, "other", "changed")
    mode = "probe <root>"
    args = ["--root", str(root), "--mode", mode]
    assert main(["--old", str(old), "--new", str(same), *args]) == 0
    assert f"{EQUAL}: {mode}" in capsys.readouterr().out
    assert main(["--old", str(old), "--new", str(other), *args]) == 1
    out = capsys.readouterr().out
    assert f"{DRIFT}: {mode}" in out
    assert "line 1: same | changed" in out
    assert "froze 2 files" in out
