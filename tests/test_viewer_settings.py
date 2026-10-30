# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W471: viewer settings (follow focus, single-key shortcuts), remembered per viewer."""

from collections.abc import Generator
from contextlib import contextmanager

import webpage
from playwright.sync_api import Page, sync_playwright

STATE = """() => ({
  follow: document.getElementById('followFocus').checked,
  keys: document.getElementById('shortcuts').checked,
})"""

# focus the second card row and report which card it is
FOCUS_SECOND = """() => {
  document.getElementById('sec-cards').open = true;
  const rows = [...document.querySelectorAll('#cardlist button[data-card]')];
  rows[1].focus();
  return rows[1].dataset.card;
}"""
SELECTED = "() => selectedId"


@contextmanager
def _viewer() -> Generator[Page]:
    """Open the served fixture fleet in a watched page; skips without a browser.

    Yields:
        The page, ready, with the Settings section open.

    """
    with webpage.served() as url, sync_playwright() as p:
        # nemik:W846: launched_page names the requests that failed if the page breaks on load
        browser, page = webpage.launched_page(p, url)
        try:
            page.click("#sec-settings > summary")
            yield page
        finally:
            browser.close()


def test_the_defaults_follow_nothing_and_keep_the_shortcuts() -> None:
    """Selection does not follow focus until asked; single-key shortcuts start on."""
    with _viewer() as page:
        state: object = page.evaluate(STATE)
    assert state == {"follow": False, "keys": True}


def test_a_changed_setting_is_remembered_across_a_reload() -> None:
    """Both boxes come back as the viewer left them."""
    with _viewer() as page:
        page.check("#followFocus")
        page.uncheck("#shortcuts")
        page.reload()
        webpage.until(page, webpage.CY_READY)
        state: object = page.evaluate(STATE)
    assert state == {"follow": True, "keys": False}


def test_following_focus_selects_the_focused_card() -> None:
    """With the setting on, focusing a card row selects that card."""
    with _viewer() as page:
        page.check("#followFocus")
        row: object = page.evaluate(FOCUS_SECOND)
        selected: object = page.evaluate(SELECTED)
    assert selected == row


def test_without_following_focus_the_selection_stays_put() -> None:
    """With the setting off, focusing a row leaves the selection where it was."""
    with _viewer() as page:
        row: object = page.evaluate(FOCUS_SECOND)
        selected: object = page.evaluate(SELECTED)
    assert selected != row
