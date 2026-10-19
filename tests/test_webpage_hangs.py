# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W715: a test that waits on a page with no clock still ends when the page breaks."""

import os
from pathlib import Path
from urllib.parse import quote

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

BREAKS = "<script>setTimeout(() => { throw new Error('boom'); }, 200);</script>"
READIES = "<script>setTimeout(() => { window.ready = true; }, 200);</script>"
READY = "() => window.ready === true"


def _serve(html: str, *, expecting: bool = False, watched: bool = True) -> str | None:
    """Open a page on `html` and wait on it with no clock; skips without a browser.

    Args:
        html: The page's markup.
        expecting: Whether to use the form that returns the page's error instead of raising.
        watched: Whether to install the error record before the page loads.

    Returns:
        The page's error message when `expecting`, else None.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).absolute()) if exe else None
            )
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        if watched:
            webpage.watch(page)
        page.goto("data:text/html," + quote(html))
        if expecting:
            found = webpage.until_expecting(page, READY)
        else:
            webpage.until(page, READY)
            found = None
        browser.close()
        return found


def test_a_page_that_throws_ends_the_wait_with_its_message() -> None:
    """The wait never sees its predicate hold, and fails with the page's own error."""
    with pytest.raises(webpage.PageBrokenError, match="boom"):
        _serve(BREAKS)


def test_a_page_that_raises_its_event_ends_the_wait_quietly() -> None:
    """A page that becomes ready returns without an error."""
    _serve(READIES)


def test_a_page_that_throws_on_purpose_hands_the_message_back() -> None:
    """The expecting form returns the page's error and leaves the verdict to the test."""
    found = _serve(BREAKS, expecting=True)
    assert found is not None
    assert "boom" in found


def test_an_unwatched_page_rests_on_its_predicate_alone() -> None:
    """With no error record the wait still ends when the page is ready, and returns no error."""
    assert _serve(READIES, expecting=True, watched=False) is None
