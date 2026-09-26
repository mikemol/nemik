"""nemik:W19: model.refresh() must not let concurrent requests redo the rebuild in parallel.

ThreadingHTTPServer calls refresh() on every request. Without a lock, several requests arriving
as a queue file changes each redo the full survey()+SHACL pass at once -- CPU contention under
the GIL that can starve the accept loop (luthen's finding: a pod stayed k8s-running but stopped
accepting connections for 10+ minutes after a burst of concurrent requests).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest import mock

from nemik.serve import Model


def write_queue(root: Path, repo: str) -> None:
    d = root / repo / ".claude"
    d.mkdir(parents=True)
    (d / "paths-forward.json").write_text(
        '{"version": 1, "project_root": "/x", "counter": 0, "waypoints": [], "residue": []}'
    )


def test_concurrent_refresh_rebuilds_once(tmp_path: Path) -> None:
    write_queue(tmp_path, "alpha")
    model = Model(tmp_path)
    real_survey = __import__("nemik.serve", fromlist=["survey"]).survey

    def slow_survey(root):
        time.sleep(0.05)  # widen the race window so concurrent callers actually overlap
        yield from real_survey(root)

    barrier = threading.Barrier(5)

    def hit():
        barrier.wait(timeout=2)
        model.refresh()

    with mock.patch("nemik.serve.survey", slow_survey):
        threads = [threading.Thread(target=hit) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

    assert model.rebuilds == 1, f"expected exactly one rebuild, got {model.rebuilds}"


def test_refresh_is_idempotent_when_nothing_changed(tmp_path: Path) -> None:
    write_queue(tmp_path, "alpha")
    model = Model(tmp_path)
    model.refresh()
    assert model.rebuilds == 1
    model.refresh()
    model.refresh()
    assert model.rebuilds == 1
