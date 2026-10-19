# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W655: each source is fetched on its own cursor; one that fails is shown, the rest draw."""

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Playwright, sync_playwright

STATUS = "() => JSON.stringify(sourceStatus)"
NODES = "() => cy.nodes('[symbol]').length"
GONE = "http://127.0.0.1:9/"


@pytest.fixture(scope="module")
def url() -> Iterator[str]:
    """Serve the fixture fleet once for the module.

    Yields:
        The served view's URL.

    """
    with webpage.served() as served:
        yield served


@pytest.fixture(scope="module")
def other() -> Iterator[str]:
    """Serve a second copy of the fleet, another origin the page may not read.

    Yields:
        The second server's URL.

    """
    with webpage.served() as served:
        yield served


def _absolute(path: str) -> str:
    """Make a path absolute.

    Args:
        path: A path, possibly relative to the test's working directory.

    Returns:
        The absolute path.

    """
    return str(Path(path).resolve())


def _page(p: Playwright, address: str, sources: list[dict[str, str]]) -> Page:
    """Open the view with a stored source list, once it has drawn.

    Args:
        p: The running Playwright.
        address: The served view.
        sources: The list the viewer has kept.

    Returns:
        The page.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        browser = p.chromium.launch(executable_path=_absolute(exe) if exe else None)
    except PlaywrightError as e:
        pytest.skip(f"chromium unavailable: {e}")
    page = browser.new_page(viewport={"width": 1700, "height": 1250})
    stored = json.dumps(json.dumps(sources))
    page.add_init_script(f"localStorage.setItem('nemik.sources', {stored});")
    page.goto(address)
    page.wait_for_function(webpage.CY_READY, timeout=0)
    return page


def _text(page: Page, script: str) -> str:
    """Run a script in the page and read its answer as text.

    Args:
        page: The page.
        script: A JavaScript function.

    Returns:
        What it returned.

    """
    answer: object = page.evaluate(script)
    return str(answer)


def _status(page: Page) -> list[str]:
    """Read each source's outcome as the page recorded it.

    Args:
        page: The page.

    Returns:
        "ok" or "unavailable: why", one per source, in list order.

    """
    answer: object = page.evaluate("() => sourceStatus")
    if not isinstance(answer, list):
        return []
    return [str(x) for x in answer]


def test_a_source_that_cannot_be_reached_is_shown_and_the_rest_draw(url: str) -> None:
    """The server itself and a closed port: the cards draw, the port is unavailable."""
    mine = [{"id": "nemik", "url": ""}, {"id": "gone", "url": GONE}]
    with sync_playwright() as p:
        page = _page(p, url, mine)
        assert int(_text(page, NODES)) > 0
        status = _status(page)
        assert status[0] == "ok"
        assert status[1].startswith("unavailable")


def test_a_source_on_another_origin_without_cors_is_unavailable(
    url: str, other: str
) -> None:
    """Another origin that sends no CORS header cannot be read; that source fails alone."""
    mine = [{"id": "nemik", "url": ""}, {"id": "other", "url": other}]
    with sync_playwright() as p:
        page = _page(p, url, mine)
        status = _status(page)
        assert status[0] == "ok"
        assert status[1].startswith("unavailable")


def test_the_status_is_shown_beside_the_source(url: str) -> None:
    """The Sources section says which source answered and which did not."""
    mine = [{"id": "nemik", "url": ""}, {"id": "gone", "url": GONE}]
    with sync_playwright() as p:
        page = _page(p, url, mine)
        page.evaluate("() => { document.getElementById('sec-sources').open = true; }")
        shown = page.locator("#sources [data-status]").all_inner_texts()
        assert shown[0] == "ok"
        assert shown[1].startswith("unavailable")
