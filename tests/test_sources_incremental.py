# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W510: a change to one repo moves one piece, and the page fetches that piece only."""

import os
import shutil
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from nemik.serve import build_static
from nemik.staticserve import handler

WITHHELD_NONE = '{"version": 1, "as_of": "test", "items": []}'
CHANGED = "gabion"
NEW_CARD = (
    '{"symbol": "W900", "title": "added by the test", "status": "ready", '
    '"blocked_on": [], "enables": []}'
)
FETCHED = "() => window.__pieceFetches.slice()"
LOAD = "async () => { await load(); }"
NODES = "() => cy.nodes('[symbol]').length"
MARK = "() => { cy.__kept = true; }"
KEPT = "() => cy.__kept === true"


def _add_a_card(queue: Path) -> None:
    """Add one ready card to a repo's queue file.

    Args:
        queue: The repo's paths-forward.json.

    """
    text = queue.read_text(encoding="utf-8")
    assert '"waypoints": [' in text
    queue.write_text(
        text.replace('"waypoints": [', '"waypoints": [' + NEW_CARD + ",", 1),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, Path]]:
    """Build a snapshot of a copy of the fleet and serve it as plain files.

    Yields:
        The served URL, and the directory holding the fleet copy to change.

    """
    root = tmp_path_factory.mktemp("incremental")
    fleet = root / "fleet"
    shutil.copytree(webpage.FLEET, fleet)
    withheld = root / "withheld.json"
    withheld.write_text(WITHHELD_NONE, encoding="utf-8")
    build_static(fleet, root / "current", withheld)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(root))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/", root
    server.shutdown()


def test_a_change_to_one_repo_fetches_only_its_piece(
    published: tuple[str, Path],
) -> None:
    """Change gabion, republish, poll: its piece and the fleet piece move, no other repo's."""
    url, root = published
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).resolve()) if exe else None
            )
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(url)
        page.wait_for_function(webpage.CY_READY, timeout=0)
        before: object = page.evaluate(FETCHED)
        page.evaluate(MARK)
        nodes_before: object = page.evaluate(NODES)
        _add_a_card(root / "fleet" / CHANGED / "paths-forward.json")
        withheld = root / "withheld.json"
        build_static(root / "fleet", root / "current", withheld)
        page.evaluate(LOAD)
        after: object = page.evaluate(FETCHED)
        nodes_after: object = page.evaluate(NODES)
        kept: object = page.evaluate(KEPT)
        browser.close()
    assert isinstance(before, list)
    assert isinstance(after, list)
    moved = [str(path) for path in after[len(before) :]]
    allowed = {f"graph/{CHANGED}.json", "graph/_fleet.json"}
    strays = [m for m in moved if m not in allowed]
    assert f"graph/{CHANGED}.json" in moved
    assert strays == []
    assert isinstance(nodes_before, int)
    assert isinstance(nodes_after, int)
    assert nodes_after == nodes_before + 1
    assert kept is True
