"""nemik:W503: a snapshot is built in a fresh process, published by one atomic flip, and skipped when quiet."""

import json
import os
import subprocess
from pathlib import Path

import installed

from nemik.serve import fleet_key, key_digest, publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_a_publish_flips_current_and_writes_the_private_files(tmp_path: Path) -> None:
    snap = publish(FLEET, tmp_path / "pub", None)
    assert snap is not None
    current = tmp_path / "pub" / "current"
    assert current.is_symlink() and (tmp_path / "pub" / os.readlink(current)) == snap
    for name in (
        "index.html",
        "hashes.json",
        "graph.json",
        "wake.json",
        "operator.json",
        "inbound.json",
        "graph.ttl",
        "metrics",
        "source-key",
    ):
        assert (snap / name).is_file(), name
    metrics = (snap / "metrics").read_text()
    assert "nemik_graph_nodes" in metrics
    assert "nemik_snapshot_published_seconds" in metrics
    hashes = json.loads((snap / "hashes.json").read_text())
    assert "operator.json" not in hashes, (
        "the private files stay out of the published hashes"
    )
    assert (snap / "source-key").read_text() == fleet_key(FLEET)


def test_a_quiet_fleet_is_not_published_again(tmp_path: Path) -> None:
    first = publish(FLEET, tmp_path / "pub", None)
    assert first is not None
    assert publish(FLEET, tmp_path / "pub", None) is None
    assert len(list((tmp_path / "pub").glob("snap-*"))) == 1


def test_a_changed_fleet_is_published_and_only_the_last_snapshots_stay(
    tmp_path: Path,
) -> None:
    base = tmp_path / "pub"
    for stale in (
        "snap-20200101T000000Z-1",
        "snap-20200102T000000Z-1",
        "snap-20200103T000000Z-1",
    ):
        (base / stale).mkdir(parents=True)
    (base / "current").symlink_to("snap-20200103T000000Z-1")
    (base / "snap-20200103T000000Z-1" / "source-key").write_text("old")
    snap = publish(FLEET, base, None, keep=2)
    assert snap is not None
    kept = sorted(p.name for p in base.glob("snap-*"))
    assert kept == ["snap-20200103T000000Z-1", snap.name]
    assert os.readlink(base / "current") == snap.name


def test_the_publish_command_runs_in_its_own_process(tmp_path: Path) -> None:
    # the point of W503: every byte of the build's graph goes back to the OS when the process exits
    cmd = [
        *installed.script("nemik-serve"),
        "--root",
        str(FLEET),
        "--publish",
        str(tmp_path / "p"),
    ]
    run = subprocess.run(
        cmd, check=True, capture_output=True, text=True, env=installed._bin()[1]
    )
    assert run.stdout.strip().startswith(str(tmp_path / "p" / "snap-"))
    again = subprocess.run(
        cmd, check=True, capture_output=True, text=True, env=installed._bin()[1]
    )
    assert again.stdout.strip() == "unchanged"


def test_the_key_digest_is_stable_for_a_key() -> None:
    assert key_digest((("a", 1),)) == key_digest((("a", 1),))
    assert key_digest((("a", 1),)) != key_digest((("a", 2),))
