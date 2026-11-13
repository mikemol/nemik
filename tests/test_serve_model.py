# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W19: model.refresh() must not let concurrent requests redo the rebuild in parallel.

ThreadingHTTPServer calls refresh() on every request. Without a lock, several requests arriving
as a queue file changes each redo the full survey()+SHACL pass at once -- CPU contention under
the GIL that can starve the accept loop (luthen's finding: a pod stayed k8s-running but stopped
accepting connections for 10+ minutes after a burst of concurrent requests).
"""

from __future__ import annotations

import os
import threading
import time
from typing import TYPE_CHECKING
from unittest import mock

from nemik.check import survey as check_survey
from nemik.serve import Model

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from rdflib import Graph

    from nemik.check import Finding

REBUILDS_AFTER_RELEASE = 2  # the first rebuild, then the one the second poke queued


def write_queue(root: Path, repo: str) -> None:
    """Write an empty queue for `repo` under `root`."""
    d = root / repo / ".claude"
    d.mkdir(parents=True)
    (d / "paths-forward.json").write_text(
        '{"version": 1, "project_root": "/x", "counter": 0, "waypoints": [], "residue": []}'
    )


def test_concurrent_refresh_rebuilds_once(tmp_path: Path) -> None:
    """Concurrent refresh rebuilds once."""
    write_queue(tmp_path, "alpha")
    model = Model(tmp_path)

    def slow_survey(
        root: Path, phases: dict[str, float] | None = None
    ) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
        time.sleep(0.05)  # widen the race window so concurrent callers actually overlap
        yield from check_survey(root, phases)

    barrier = threading.Barrier(5)

    def hit() -> None:
        barrier.wait(timeout=2)
        model.refresh()

    with mock.patch("nemik.serve.survey", slow_survey):
        threads = [threading.Thread(target=hit) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            # a cap, not an expectation: at host load ~100 one rebuild outlasted a 2 s join and the
            # assertion read 0 rebuilds that were still running (nemik:W339's gate, 2026-10-13)
            t.join(timeout=120)

    assert model.rebuilds == 1, f"expected exactly one rebuild, got {model.rebuilds}"


def test_refresh_is_idempotent_when_nothing_changed(tmp_path: Path) -> None:
    """Refresh is idempotent when nothing changed."""
    write_queue(tmp_path, "alpha")
    model = Model(tmp_path)
    model.refresh()
    assert model.rebuilds == 1
    model.refresh()
    model.refresh()
    assert model.rebuilds == 1


def test_poke_serves_stale_while_rebuilding(tmp_path: Path) -> None:
    """nemik:W69: after the first build, a changed export rebuilds in the background.

    nemik:W2163: no wall clock decides this test. The background rebuild says when it has entered
    its survey (an event); a poke that blocked on it would never reach the next line, and the
    rebuild is waited for by calling refresh(), which takes the model's lock and so returns only
    once the build is complete, whoever ran it.
    """
    write_queue(tmp_path, "alpha")
    model = Model(tmp_path)
    model.poke()
    assert model.rebuilds == 1
    entered = threading.Event()
    released = threading.Event()

    def gated_survey(
        root: Path, phases: dict[str, float] | None = None
    ) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
        entered.set()
        released.wait()
        yield from check_survey(root, phases)

    q = tmp_path / "alpha" / ".claude" / "paths-forward.json"
    os.utime(q, ns=(q.stat().st_atime_ns, q.stat().st_mtime_ns + 10**9))
    with mock.patch("nemik.serve.survey", gated_survey):
        model.poke()
        entered.wait()  # the rebuild is running in the background, holding the lock
        model.poke()  # a second request while the rebuild is in flight starts nothing new
        assert model.rebuilds == 1
        released.set()
        model.refresh()  # waits on the lock until the one background rebuild is complete
    assert model.rebuilds == REBUILDS_AFTER_RELEASE
