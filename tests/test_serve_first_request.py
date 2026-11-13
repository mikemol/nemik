# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2163: a request that arrives while the first document is built waits for it.

The page's first loads hit the live server together. The first request builds the model
synchronously (poke() calls refresh() while `rebuilds` is 0), but refresh() raised `rebuilds` and
set the cache key BEFORE it built the JSON document, so a request that arrived during that build
passed poke() (rebuilds was nonzero) and was served the initial `b"{}"` and an empty doc: the page
read `nodes` of `{}`, threw "Cannot read properties of undefined (reading 'map')", and a cold,
loaded gate refused an unrelated stack (test_page_landings, 2026-11-13). The interleaving is forced
here with events, not with load: a second request is made while to_json is held open.
"""

import json
import threading
from typing import TYPE_CHECKING
from unittest import mock

from nemik import serve
from nemik.serve import Model

if TYPE_CHECKING:
    from pathlib import Path

    from rdflib import Graph

    from nemik.check import Finding
    from nemik.serve import ViewDoc

GUARD_SECONDS = 30  # a cap so a failing test cannot hang, not an expectation
EARLY_SECONDS = 0.5  # how long a request is given to (wrongly) return mid-build


def write_queue(root: Path, repo: str) -> None:
    """Write an empty queue for `repo` under `root`."""
    d = root / repo / ".claude"
    d.mkdir(parents=True)
    (d / "paths-forward.json").write_text(
        '{"version": 1, "project_root": "/x", "counter": 0, "waypoints": [], "residue": []}',
        encoding="utf-8",
    )


def test_a_request_during_the_first_document_waits_for_it(tmp_path: Path) -> None:
    """Serve the built document, never the initial empty payload, to a request made mid-build."""
    write_queue(tmp_path, "alpha")
    model = Model(tmp_path)
    inside, release, observed = (threading.Event() for _ in range(3))
    seen: dict[str, bytes] = {}
    real = serve.to_json

    def held(
        g: Graph, findings: dict[str, list[Finding]], numbers: Graph | None = None
    ) -> ViewDoc:
        inside.set()
        release.wait(timeout=GUARD_SECONDS)
        return real(g, findings, numbers)

    def second_request() -> None:
        model.poke()  # what a request does before it serves model.payload
        seen["payload"] = model.payload
        observed.set()

    with mock.patch("nemik.serve.to_json", held):
        first = threading.Thread(target=model.poke)
        first.start()
        assert inside.wait(timeout=GUARD_SECONDS), "the first build never reached to_json"
        second = threading.Thread(target=second_request)
        second.start()
        returned_early = observed.wait(timeout=EARLY_SECONDS)
        release.set()
        first.join(timeout=GUARD_SECONDS)
        second.join(timeout=GUARD_SECONDS)

    assert not returned_early, "a request returned while the first document was being built"
    served: dict[str, object] = json.loads(seen["payload"])
    assert "nodes" in served, "it was served the initial empty payload"
    assert model.rebuilds == 1
