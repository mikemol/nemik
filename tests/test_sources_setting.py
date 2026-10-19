# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W654: the viewer's source list is kept in this browser, nemik's pieces by default."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Playwright, sync_playwright

OPEN = "() => { document.getElementById('sec-sources').open = true; }"
SOURCES = "() => JSON.stringify(sources)"
KEPT = "() => localStorage.getItem('nemik.sources')"
DEFAULT = '[{"id":"nemik","url":""}]'
INPUTS_PER_SOURCE = 2
BLOCKED = """Object.defineProperty(window, 'localStorage',
  { get() { throw new Error('storage blocked'); } });"""


@pytest.fixture(scope="module")
def url() -> Iterator[str]:
    """Serve the fixture fleet once for the module.

    Yields:
        The served view's URL.

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


def _eval(page: Page, script: str) -> str:
    """Run a script in the page and read its answer as text.

    Args:
        page: The page.
        script: A JavaScript function returning a string.

    Returns:
        What it returned.

    """
    answer: object = page.evaluate(script)
    return str(answer)


def _page(p: Playwright, address: str, before: str = "") -> Page:
    """Open the view with its Sources section open, once it has drawn.

    Args:
        p: The running Playwright.
        address: The served view.
        before: A script to run in the page before its own scripts do.

    Returns:
        The page.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        browser = p.chromium.launch(executable_path=_absolute(exe) if exe else None)
    except PlaywrightError as e:
        pytest.skip(f"chromium unavailable: {e}")
    page = browser.new_page(viewport={"width": 1700, "height": 1250})
    if before:
        page.add_init_script(before)
    page.goto(address)
    page.wait_for_function(webpage.CY_READY, timeout=0)
    page.evaluate(OPEN)
    return page


def test_the_default_is_one_entry_for_nemiks_own_pieces(url: str) -> None:
    """Nothing stored: one source named nemik with an empty URL, shown as two inputs."""
    with sync_playwright() as p:
        page = _page(p, url)
        assert _eval(page, SOURCES) == DEFAULT
        assert page.locator("#sources input").count() == INPUTS_PER_SOURCE


def test_an_added_source_is_kept_and_survives_a_reload(url: str) -> None:
    """Add a source and name it; the list is stored and read back after a reload."""
    with sync_playwright() as p:
        page = _page(p, url)
        page.click("#addsource")
        page.locator("#sources input").nth(2).fill("other")
        page.locator("#sources input").nth(3).fill("https://example.test/pieces")
        stored = '[{"id":"nemik","url":""},'
        stored += '{"id":"other","url":"https://example.test/pieces"}]'
        assert _eval(page, KEPT) == stored
        page.reload()
        page.wait_for_function(webpage.CY_READY, timeout=0)
        assert _eval(page, SOURCES) == stored


def test_the_last_source_cannot_be_removed(url: str) -> None:
    """With one source left, remove does nothing: the viewer always has a source."""
    with sync_playwright() as p:
        page = _page(p, url)
        page.click("#sources button[data-remove]")
        assert _eval(page, SOURCES) == DEFAULT


def test_a_stored_value_that_is_not_a_source_list_leaves_the_default(url: str) -> None:
    """A reading of the wrong shape is ignored, not trusted."""
    junk = "localStorage.setItem('nemik.sources', '[{\"id\": 3}]');"
    with sync_playwright() as p:
        page = _page(p, url, junk)
        assert _eval(page, SOURCES) == DEFAULT


def test_storage_that_throws_leaves_the_default(url: str) -> None:
    """A private window can make localStorage throw; the default still stands."""
    with sync_playwright() as p:
        page = _page(p, url, BLOCKED)
        assert _eval(page, SOURCES) == DEFAULT
