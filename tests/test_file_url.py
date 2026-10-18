# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W657: opened from a file: URL the page says why it is empty and what to do."""

import os
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from nemik.serve import build_static

WITHHELD_NONE = '{"version": 1, "as_of": "test", "items": []}'
SAYS = "() => document.getElementById('stat').innerText.includes('opened from a file')"


def test_a_page_opened_from_a_file_url_says_to_serve_the_folder(
    tmp_path: Path,
) -> None:
    """Chromium will not fetch a sibling file from file:, so the page names the way out."""
    withheld = tmp_path / "withheld.json"
    withheld.write_text(WITHHELD_NONE)
    out = tmp_path / "current"
    build_static(webpage.FLEET, out, withheld)
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).resolve()) if exe else None
            )
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        failures: list[str] = []

        def note(err: object) -> None:
            failures.append(str(err))

        page.on("pageerror", note)
        page.goto((out / "index.html").as_uri())
        page.wait_for_function(SAYS)
        shown = page.inner_text("#stat")
        browser.close()
    assert "http.server" in shown
    assert failures == []
