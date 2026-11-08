# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2064: a build the memory limit killed leaves a dir, and the next publish removes it."""

from pathlib import Path

from nemik.serve import publish, remove_partial_snaps

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_a_dir_without_source_key_is_removed_and_a_complete_one_stays(
    tmp_path: Path,
) -> None:
    """A partial dir goes, a complete one stays."""
    partial = tmp_path / "snap-20200101T000000Z-7"
    partial.mkdir()
    (partial / "graph.json").write_text("half")
    complete = tmp_path / "snap-20200102T000000Z-8"
    complete.mkdir()
    (complete / "source-key").write_text("k")
    assert remove_partial_snaps(tmp_path) == 1
    assert not partial.exists()
    assert complete.is_dir()


def test_a_missing_base_removes_nothing(tmp_path: Path) -> None:
    """A base that does not exist yet is not an error."""
    assert remove_partial_snaps(tmp_path / "absent") == 0


def test_a_publish_removes_the_orphan_a_killed_build_left(tmp_path: Path) -> None:
    """A publish over a base holding an orphan leaves only complete snapshots."""
    base = tmp_path / "pub"
    orphan = base / "snap-20200101T000000Z-99"
    orphan.mkdir(parents=True)
    (orphan / "index.html").write_text("half")
    snap = publish(FLEET, base, None)
    assert snap is not None
    assert not orphan.exists()
    assert [p.name for p in base.glob("snap-*")] == [snap.name]


def test_a_quiet_fleet_still_clears_an_orphan(tmp_path: Path) -> None:
    """The cleanup runs before the unchanged-fleet exit."""
    base = tmp_path / "pub"
    assert publish(FLEET, base, None) is not None
    orphan = base / "snap-20200101T000000Z-99"
    orphan.mkdir()
    assert publish(FLEET, base, None) is None
    assert not orphan.exists()
