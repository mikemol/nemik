# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1086: a pod with no snapshot of its own serves the last good one kept on the claim."""

from pathlib import Path

from nemik.lastgood import KEEP, LAST, restore, save

KEY = "source-key"


def _snapshot(base: Path, name: str, key: str) -> Path:
    snap = base / name
    snap.mkdir(parents=True)
    (snap / KEY).write_text(key)
    (snap / "graph.json").write_text("{}")
    return snap


def test_a_saved_snapshot_is_restored_into_an_empty_publish_directory(
    tmp_path: Path,
) -> None:
    """The new pod's /srv/current serves the old pod's last build at once."""
    keep, base = tmp_path / "claim", tmp_path / "srv"
    base.mkdir()
    save(_snapshot(tmp_path, "snap-a", "k1"), keep)
    assert restore(base, keep) is True
    assert (base / "current" / KEY).read_text() == "k1"
    assert (base / "current" / "graph.json").is_file()


def test_nothing_is_restored_over_a_snapshot_the_pod_published(tmp_path: Path) -> None:
    """A pod that already has a current keeps it; the kept copy never replaces a fresher build."""
    keep, base = tmp_path / "claim", tmp_path / "srv"
    save(_snapshot(tmp_path, "snap-a", "old"), keep)
    own = _snapshot(base, "snap-own", "new")
    (base / "current").symlink_to(own.name)
    assert restore(base, keep) is False
    assert (base / "current" / KEY).read_text() == "new"


def test_a_claim_with_nothing_kept_restores_nothing(tmp_path: Path) -> None:
    """The first pod ever: no kept copy, so the old behaviour (wait for the build) stands."""
    base = tmp_path / "srv"
    base.mkdir()
    assert restore(base, tmp_path / "claim") is False
    assert not (base / "current").exists()


def test_only_the_latest_copies_are_kept(tmp_path: Path) -> None:
    """Each save leaves last-good at the newest, and the claim holds no more than KEEP copies."""
    keep = tmp_path / "claim"
    for index in range(KEEP + 2):
        save(_snapshot(tmp_path, f"snap-{index}", f"k{index}"), keep)
    copies = [p for p in keep.glob(f"{LAST}-*") if p.is_dir()]
    assert len(copies) <= KEEP
    assert (keep / LAST / KEY).read_text() == f"k{KEEP + 1}"
