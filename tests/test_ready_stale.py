# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W489, github:R28: nemik_ready_stale counts each repo's stale ready cards, 0 where none."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik import metrics
from nemik.metrics import ready_stale_lines

NOW = datetime(2030, 1, 2, 12, 0, tzinfo=UTC)
WEEK = 7 * 86400.0


def _fleet(root: Path) -> None:
    for repo in ("a", "b"):
        claude = root / repo / ".claude"
        claude.mkdir(parents=True)
        (claude / "paths-forward.json").write_text("{}")


def _learned(root: Path, now: str) -> tuple[float, dict[str, list[tuple[float, str]]]]:
    del root, now
    return WEEK, {"a": [(9 * 86400.0, "W1"), (8 * 86400.0, "W2")]}


def _unlearned(
    root: Path, now: str
) -> tuple[float, dict[str, list[tuple[float, str]]]]:
    del root, now
    return -1.0, {}


def test_every_queue_bearing_repo_gets_its_count_and_a_clean_one_gets_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The per-repo count the ready-neither report lists; repo b has none late, so it reads 0."""
    monkeypatch.setattr(metrics, "ready_neither", _learned)
    _fleet(tmp_path)
    assert ready_stale_lines(tmp_path, NOW) == [
        "# TYPE nemik_ready_stale gauge",
        'nemik_ready_stale{repo="a"} 2',
        'nemik_ready_stale{repo="b"} 0',
    ]


def test_an_unlearned_bound_publishes_no_sample_not_a_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fewer than ten finished small cards learn no bound; a 0 there would claim a clean queue."""
    monkeypatch.setattr(metrics, "ready_neither", _unlearned)
    _fleet(tmp_path)
    assert ready_stale_lines(tmp_path, NOW) == ["# TYPE nemik_ready_stale gauge"]
