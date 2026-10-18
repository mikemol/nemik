# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W502: the view works from a published snapshot and the file server alone.

A snapshot is built by the static build from the fixture fleet, served by nemik-static (no model, no
rdflib), and opened in a browser: the page assembles the graph from hashes.json and the pieces, draws
it, and fetches nothing the server cannot answer from a file.
"""

import subprocess
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import installed
import pytest
import webpage

from nemik.staticserve import handler

sync_api = pytest.importorskip("playwright.sync_api")

WITHHELD_NONE = '{"version": 1, "as_of": "test", "items": []}'


@pytest.fixture(scope="module")
def snapshot_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    root = tmp_path_factory.mktemp("published")
    withheld = root / "withheld.json"
    withheld.write_text(WITHHELD_NONE)
    out = root / "current"
    build = [
        *installed.script("nemik-serve"),
        "--root",
        str(webpage.FLEET),
        "--static",
        str(out),
        "--withheld",
        str(withheld),
    ]
    subprocess.run(build, check=True, env=installed._bin()[1], capture_output=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(root))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


def test_the_view_draws_from_the_snapshot_files_alone(snapshot_url: str) -> None:
    with sync_api.sync_playwright() as p:
        browser, page = webpage.open_page(p, snapshot_url)
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.wait_for_function(
            "() => document.getElementById('stat').innerText.includes('waypoints')",
            timeout=60000,
        )
        drawn = page.evaluate("() => cy.nodes('[symbol]').length")
        fetched = page.evaluate("() => window.__pieceFetches.length")
        stat = page.inner_text("#stat")
        browser.close()
    assert drawn > 10, "the page drew no cards from the snapshot"
    assert fetched > 1, "the page did not assemble the graph from pieces"
    assert "waypoints" in stat
    assert errors == []
