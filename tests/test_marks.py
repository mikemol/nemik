"""nemik:W234/W236: marks are read from the writer's file, and a stale one is never read as current."""

from __future__ import annotations

import json
from pathlib import Path

from nemik.marks import DERIVED, MARK, STALE, policy_version, provenance, read

NOW = "2026-10-08T12:00:00Z"
VERSION = "v1"


def _mark(as_of: str, version: str = VERSION) -> dict[str, object]:
    return {"as_of": as_of, "policy_version": version, "symbol": "W1", "verdict": {}}


def test_no_mark_is_derived() -> None:
    assert provenance(None, NOW, VERSION) == DERIVED


def test_a_fresh_mark_judged_by_this_policy_is_a_mark() -> None:
    assert provenance(_mark("2026-10-08T11:30:00Z"), NOW, VERSION) == MARK


def test_a_mark_older_than_the_policy_max_age_is_stale() -> None:
    assert provenance(_mark("2026-10-08T10:00:00Z"), NOW, VERSION) == STALE


def test_a_mark_judged_by_another_policy_is_stale_however_fresh() -> None:
    assert provenance(_mark(NOW, "v0"), NOW, VERSION) == STALE


def test_an_unreadable_as_of_is_stale_never_current() -> None:
    assert provenance(_mark("yesterday"), NOW, VERSION) == STALE
    assert provenance(_mark("2026-10-08T11:59:00"), NOW, VERSION) == STALE


def test_the_latest_mark_per_symbol_wins_and_bad_lines_are_counted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "paths-forward.marks.jsonl"
    older, newer = _mark("2026-10-08T10:00:00Z"), _mark("2026-10-08T11:00:00Z")
    path.write_text(
        "\n".join([json.dumps(older), "not json", json.dumps(newer), '{"no": 1}', ""]),
        encoding="utf-8",
    )
    marks, unreadable = read(path)
    assert marks["W1"] == newer
    assert unreadable == 2


def test_an_absent_marks_file_reads_empty(tmp_path: Path) -> None:
    assert read(tmp_path / "none.jsonl") == ({}, 0)


def test_the_policy_version_is_a_sha256_of_the_shipped_policy() -> None:
    assert len(policy_version()) == 64
