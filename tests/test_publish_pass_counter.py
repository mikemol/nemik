# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2517: every publish pass counts, built or skipped, in the file and in /metrics."""

from pathlib import Path

import pytest

from nemik.serve import COUNTS_FILE, publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"
POD = "nemik-abc-1"


def _counter(base: Path, outcome: str) -> str:
    # the counter sample of the CURRENT snapshot's /metrics for one outcome
    text = (base / "current" / "metrics").read_text(encoding="utf-8")
    wanted = f'nemik_publish_passes_total{{outcome="{outcome}",pod="{POD}"}} '
    found = [line for line in text.splitlines() if line.startswith(wanted)]
    assert len(found) == 1
    return found[0].removeprefix(wanted)


def test_a_build_then_two_skips_count_one_built_and_two_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The counter lives in the file beside the snapshots and in the served /metrics."""
    monkeypatch.setenv("NEMIK_POD", POD)
    base = tmp_path / "pub"
    assert publish(FLEET, base, None) is not None
    assert (base / COUNTS_FILE).read_text(encoding="utf-8") == "built 1\nskipped 0\n"
    assert (_counter(base, "built"), _counter(base, "skipped")) == ("1", "0")
    assert publish(FLEET, base, None) is None
    assert publish(FLEET, base, None) is None
    assert (base / COUNTS_FILE).read_text(encoding="utf-8") == "built 1\nskipped 2\n"
    assert (_counter(base, "built"), _counter(base, "skipped")) == ("1", "2")


def test_the_served_metrics_keep_one_copy_of_the_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skip replaces the counter lines, never appends a second set."""
    monkeypatch.setenv("NEMIK_POD", POD)
    base = tmp_path / "pub"
    publish(FLEET, base, None)
    publish(FLEET, base, None)
    text = (base / "current" / "metrics").read_text(encoding="utf-8")
    assert text.count("# TYPE nemik_publish_passes_total counter") == 1
    assert text.count("nemik_publish_passes_total{") == len(("built", "skipped"))
    assert "nemik_snapshot_published_seconds" in text


def test_an_unwritable_counts_file_never_fails_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The counter observes the publish; a directory where its file should be is a warning."""
    monkeypatch.setenv("NEMIK_POD", POD)
    base = tmp_path / "pub"
    (base / COUNTS_FILE).mkdir(parents=True)
    assert publish(FLEET, base, None) is not None
    assert (base / "current" / "metrics").is_file()
