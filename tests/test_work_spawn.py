# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: nemik-work's spawn keeps its timeout semantics, with "none" spelled -1.

`int | None` and Optional are Codon walls, so _spawn takes `timeout: int` and NO_LIMIT (-1) means
the tool may take as long as it likes, which is how the writer was always run. run_writer is the
NO_LIMIT caller and run_committer passes COMMITTER_TIMEOUT. Where the tools are and where scratch
directories go is an Env (the pinned Codon has no sys.executable or tempfile): a tool that is not
in its directory is status 127, and a tool that fails to start is FAILED (71) with the error on
stderr, never read as a timeout.
"""

from typing import TYPE_CHECKING

import pytest

from nemik import work
from nemik.spawn import FAILED, NO_LIMIT, Completed

if TYPE_CHECKING:
    from pathlib import Path

SEEN: list[tuple[object, object]] = []
NOT_INSTALLED = 127


def _fake_capture(argv: list[str], timeout: int, root: str) -> Completed:
    """Record the timeout and root it is given and answer success.

    Returns:
        A successful Completed.

    """
    SEEN.append((timeout, root))
    return Completed(argv, 0, "out", "")


def _installed(tmp_path: Path, tool: str) -> work.Env:
    """Make `tool` exist in a directory, as the spawn looks for it.

    Returns:
        An Env whose tool directory and temp root are that directory.

    """
    (tmp_path / tool).write_text("", encoding="utf-8")
    return work.Env(str(tmp_path), str(tmp_path))


def test_no_limit_runs_the_writer_with_no_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pass NO_LIMIT and the Env's temp root through to capture, which runs without `timeout`."""
    SEEN.clear()
    env = _installed(tmp_path, "mikemol-paths-forward")
    monkeypatch.setattr(work, "capture", _fake_capture)
    code, out = work.run_writer(["--check"], env)
    assert (code, out) == (0, "out")
    assert [(NO_LIMIT, str(tmp_path))] == SEEN


def test_the_committer_keeps_its_twenty_second_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pass COMMITTER_TIMEOUT through unchanged."""
    SEEN.clear()
    env = _installed(tmp_path, "mikemol-commit")
    monkeypatch.setattr(work, "capture", _fake_capture)
    code, _ = work.run_committer(["REPO", "--in-gate", "--json"], env)
    assert code == 0
    assert [(work.COMMITTER_TIMEOUT, str(tmp_path))] == SEEN


def test_a_missing_tool_is_127_and_a_failed_start_is_its_own_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Say 127 for a tool not in the directory and FAILED, with the error, for one that fails."""
    env = work.Env(str(tmp_path), str(tmp_path))
    assert work.run_committer(["x"], env) == (NOT_INSTALLED, "")

    def failed(argv: list[str], _timeout: int, _root: str) -> Completed:
        raise OSError(len(argv), "boom")

    env = _installed(tmp_path, "mikemol-commit")
    monkeypatch.setattr(work, "capture", failed)
    assert work.run_committer(["x"], env) == (FAILED, "")
    said = capsys.readouterr().err
    assert "could not run mikemol-commit" in said
    assert "boom" in said
