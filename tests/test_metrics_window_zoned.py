# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1127: the windows the hourly gauges build are zoned, so the resolver does not refuse them.

luthen's relay of nemik-metrics failed every run with 'names a time with no zone' for about 21 hours
(2026-10-27) because the gauges built `now - 1 day` as a local naive time and history.resolve
refuses one; the unit tests replaced the history calls and never saw it. These tests record the
window each gauge builds and hand it to the real resolver.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik import history, metrics
from nemik.metrics import commit_lines, completed_lines, reopened_lines

NOW = datetime(2030, 1, 2, 12, 0, tzinfo=UTC)


def _fleet(root: Path) -> None:
    """One repo, r, with a queue file (no git history is needed to build a window)."""
    claude = root / "r" / ".claude"
    claude.mkdir(parents=True)
    (claude / "paths-forward.json").write_text("{}")


def test_the_hourly_gauges_build_windows_the_resolver_accepts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each gauge's window goes through history.resolve without the no-zone refusal."""
    seen: list[str] = []

    def record(repo: Path, since: str) -> int:
        del repo
        seen.append(since)
        return 0

    monkeypatch.setattr(history, "commits_since", record)
    monkeypatch.setattr(history, "reopened_since", record)
    monkeypatch.setattr(metrics, "completed_in", record)
    _fleet(tmp_path)
    commit_lines(tmp_path, NOW)
    completed_lines(tmp_path, NOW)
    reopened_lines(tmp_path, NOW)
    assert len(seen) == len({"commits", "completed", "reopened"})
    for since in seen:
        history.resolve(tmp_path, since)
