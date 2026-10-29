# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W472: one keymap table drives the keys and the ? overlay, and / jumps to a card."""

from collections.abc import Generator
from contextlib import contextmanager

import webpage
from playwright.sync_api import Page, sync_playwright

EVERY_KEY_HAS_A_HANDLER = (
    "() => KEYMAP.every(k => typeof ACTIONS[k.action] === 'function')"
)
ROWS = "() => document.querySelectorAll('#keylist dt').length === KEYMAP.length"
OPEN = "() => !document.getElementById('keyhelp').hidden"
A_DRAWN = "data.nodes.find(n => n.cite && cy.getElementById(n.id).length)"
A_CITE = f"() => {A_DRAWN}.cite"
ITS_ID = f"() => {A_DRAWN}.id"
SELECTED = "() => selectedId"


@contextmanager
def _viewer() -> Generator[Page]:
    """Open the served fixture fleet in a watched page; skips without a browser.

    Yields:
        The page, ready.

    """
    with webpage.served() as url, sync_playwright() as p:
        # nemik:W846: launched_page names the requests that failed if the page breaks on load
        browser, page = webpage.launched_page(p, url)
        try:
            yield page
        finally:
            browser.close()


def test_every_key_in_the_table_has_a_handler_and_a_help_row() -> None:
    """The table is the one source: each key has an action, and the overlay has a row for each."""
    with _viewer() as page:
        handled: object = page.evaluate(EVERY_KEY_HAS_A_HANDLER)
        rows: object = page.evaluate(ROWS)
    assert handled is True
    assert rows is True


def test_question_mark_opens_the_overlay_and_escape_closes_it() -> None:
    """? shows the shortcuts and Escape hides them."""
    with _viewer() as page:
        page.keyboard.press("?")
        opened: object = page.evaluate(OPEN)
        page.keyboard.press("Escape")
        closed: object = page.evaluate(OPEN)
    assert opened is True
    assert closed is False


def test_the_shortcut_setting_turns_the_keys_off() -> None:
    """With single-key shortcuts off, ? opens nothing (WCAG 2.1.4)."""
    with _viewer() as page:
        page.click("#sec-settings > summary")
        page.uncheck("#shortcuts")
        page.locator("body").press("?")
        opened: object = page.evaluate(OPEN)
    assert opened is False


def test_slash_jumps_to_a_card_by_its_cite() -> None:
    """/ opens the jump box, and Enter on a cite selects that card."""
    with _viewer() as page:
        cite: object = page.evaluate(A_CITE)
        card: object = page.evaluate(ITS_ID)
        page.keyboard.press("/")
        page.fill("#jump", str(cite))
        page.keyboard.press("Enter")
        selected: object = page.evaluate(SELECTED)
    assert selected == card
