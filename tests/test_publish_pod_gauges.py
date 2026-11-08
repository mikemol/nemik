# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2065: the publish gauges name the pod and count the partial dirs a publish removed."""

from pathlib import Path

import pytest

from nemik.serve import publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_publish_gauge_names_the_pod_and_the_removal_gauge_counts_orphans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each gauge carries the pod label, and the removal count is the orphans cleared."""
    monkeypatch.setenv("NEMIK_POD", "nemik-abc-1")
    base = tmp_path / "pub"
    for name in ("snap-20200101T000000Z-1", "snap-20200102T000000Z-2"):
        (base / name).mkdir(parents=True)
    snap = publish(FLEET, base, None)
    assert snap is not None
    lines = (snap / "metrics").read_text().splitlines()
    name = "nemik_snapshot_published_seconds"
    published = [ln for ln in lines if ln.startswith(name)]
    assert len(published) == 1
    assert published[0].startswith(name + '{pod="nemik-abc-1"} ')
    assert 'nemik_snapshot_partial_removed{pod="nemik-abc-1"} 2' in lines


def test_a_clean_base_reports_zero_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A base with no orphan publishes a removal count of 0."""
    monkeypatch.setenv("NEMIK_POD", "p")
    snap = publish(FLEET, tmp_path / "pub", None)
    assert snap is not None
    text = (snap / "metrics").read_text()
    assert 'nemik_snapshot_partial_removed{pod="p"} 0' in text
