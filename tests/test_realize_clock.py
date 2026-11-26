# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1890: realize reads the judging instant with `time`, in the writer's own stamp format."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mikemol.pathsforward.lock import stamp

from nemik import realize

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

EPOCH = 1_700_000_000


def test_judged_hands_the_writers_stamp_of_the_clock_to_the_judge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The instant is the clock's UTC second in `YYYY-MM-DDTHH:MM:SSZ`, as lock.stamp writes it."""
    seen: list[str] = []
    real_gmtime = time.gmtime

    def fake_verdicts(
        _repo: str, _path: Path, _root: Path, now: str
    ) -> list[dict[str, object]]:
        seen.append(now)
        return []

    monkeypatch.setattr(realize, "verdicts", fake_verdicts)
    monkeypatch.setattr(time, "gmtime", lambda: real_gmtime(EPOCH))
    assert realize.judged([("r", tmp_path / "q.json")], tmp_path) == []
    assert seen == [stamp(datetime.fromtimestamp(EPOCH, UTC))]
    assert seen[0].endswith("Z")
