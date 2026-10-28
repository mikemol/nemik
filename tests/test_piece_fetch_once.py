# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1140: two load rounds that overlap fetch each piece of the graph once, not once each."""

import functools
import http.server
import json
import threading
from pathlib import Path
from typing import cast

import webpage
from playwright.sync_api import sync_playwright

from nemik.serve import build_static

READY = "() => typeof data !== 'undefined' && data"
# Both rounds begin before either piece has come back, which is what a poll that starts while a
# slow first load is still waiting does under gate load. The cache is emptied first so every piece
# is asked for again.
OVERLAP = """async () => {
  for (const key of Object.keys(pieceCache)) delete pieceCache[key];
  window.__pieceFetches.length = 0;
  await Promise.all([sourceGraph({url: ""}), sourceGraph({url: ""})]);
  return [...window.__pieceFetches];
}"""
SEVERAL = 3  # the fleet piece and at least two repos


def test_two_overlapping_rounds_fetch_each_piece_once(tmp_path: Path) -> None:
    """The cache holds the promise of a piece, so the second round shares the first's fetch."""
    withheld = tmp_path / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp_path / "out"
    build_static(webpage.FLEET, out, withheld)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(out)
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    try:
        with sync_playwright() as p:
            browser, page = webpage.launched_page(p, url, READY)
            fetched = cast("list[str]", webpage.evaluate_value(page, OVERLAP))
            browser.close()
    finally:
        httpd.shutdown()
    assert len(fetched) >= SEVERAL
    assert len(set(fetched)) == len(fetched), sorted(fetched)
