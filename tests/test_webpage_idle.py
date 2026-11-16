# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2235: a page waiting for a state that never comes ends by its own frames."""

from urllib.parse import quote

import pytest
import webpage
from playwright.sync_api import sync_playwright

IDLE_PAGE = "<body><p>nothing here will ever change</p></body>"
BUSY_PAGE = (
    "<body><script>"
    "let n = 0;"
    "const tick = () => {"
    " document.body.setAttribute('data-n', String(++n));"
    " if (n > 200) {"
    "  const done = document.createElement('i'); done.id = 'done';"
    "  document.body.appendChild(done);"
    " } else { requestAnimationFrame(tick); }"
    "};"
    "requestAnimationFrame(tick);"
    "</script></body>"
)
NEVER = "() => document.getElementById('never') !== null"
DONE = "() => document.getElementById('done') !== null"
NO_PROGRESS = "no progress: 30 animation"


def data_url(html: str) -> str:
    """Give a data: address that serves `html`.

    Returns:
        The address.

    """
    return "data:text/html," + quote(html)


def test_a_page_that_waits_for_nothing_fails_naming_the_lack_of_progress() -> None:
    """A selector that never appears ends the wait after 30 quiet frames, with no clock set."""
    with sync_playwright() as p:
        browser, page = webpage.launched_page(p, data_url(IDLE_PAGE), "() => true")
        try:
            with pytest.raises(webpage.PageBrokenError, match=NO_PROGRESS):
                webpage.until(page, NEVER, 30)
        finally:
            browser.close()


def test_a_page_that_keeps_changing_is_not_called_idle() -> None:
    """A page that mutates every frame for 200 frames outlasts a 30-frame limit and finishes."""
    with sync_playwright() as p:
        browser, page = webpage.launched_page(p, data_url(BUSY_PAGE), "() => true")
        try:
            webpage.until(page, DONE, 30)
        finally:
            browser.close()
