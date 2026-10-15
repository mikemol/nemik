"""nemik:W503: a snapshot is built in a fresh process, published by one atomic flip, and skipped when quiet."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import installed

from nemik.serve import fleet_key, publish

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


def _copy_fleet(tmp_path: Path) -> Path:
    root = tmp_path / "fleet"
    shutil.copytree(FLEET, root)
    return root


def test_a_rewrite_that_changes_nothing_is_not_a_change(tmp_path: Path) -> None:
    # luthen's export rewrites its files every minute; a build costs real CPU, so only CONTENT counts
    root = _copy_fleet(tmp_path)
    assert publish(root, tmp_path / "pub", None) is not None
    files = list(root.glob("*/paths-forward.*"))  # the export layout
    assert files, "the fixture fleet has no queue or ledger files to touch"
    for queue in files:
        os.utime(queue, ns=(time.time_ns(), time.time_ns() + 10**9))
    assert publish(root, tmp_path / "pub", None) is None


def test_a_change_of_content_is_published(tmp_path: Path) -> None:
    root = _copy_fleet(tmp_path)
    first = publish(root, tmp_path / "pub", None)
    assert first is not None
    queue = next(root.glob("*/paths-forward.json"))
    queue.write_text(queue.read_text() + "\n")
    assert fleet_key(root) != (first / "source-key").read_text()
    second = publish(root, tmp_path / "pub", None)
    assert second is not None and second != first


def test_a_publish_keeps_the_build_caches_beside_the_snapshots(tmp_path: Path) -> None:
    # W518: the next fresh process starts warm from these
    assert publish(FLEET, tmp_path / "pub", None) is not None
    cache = tmp_path / "pub" / ".cache" / "build-caches.pickle"
    assert cache.is_file() and cache.stat().st_size > 0
