# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W798: choosing a card-list order opens the Cards section, so the choice shows.

The order radios and the 1 to 6 keys act on the Cards list, which lives in a side-panel section that
is closed by default. A viewer who picked an order saw nothing change (operator report 2026-10-20).
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error, Page, ViewportSize, sync_playwright

VIEWPORT = ViewportSize(width=1700, height=1250)
READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0"
SECTION = "#sec-cards"


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """Serve the fixture fleet.

    Yields:
        The page's URL.

    """
    with webpage.served() as url:
        yield url


@pytest.fixture()
def page(server: str) -> Iterator[Page]:
    """Open the page in the pinned browser, once its graph is drawn.

    Yields:
        The page.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).absolute()) if exe else None
            )
        except Error as error:
            pytest.skip(f"chromium unavailable: {error}")
        opened = browser.new_page(viewport=VIEWPORT)
        webpage.watch(opened)
        opened.goto(server)
        webpage.until(opened, READY)
        yield opened
        browser.close()


def _is_open(page: Page) -> bool:
    """Say whether the Cards section is open.

    Returns:
        True when the details element carries its open attribute.

    """
    return page.locator(SECTION).get_attribute("open") is not None


def test_the_cards_section_starts_closed(page: Page) -> None:
    """The default this test works against: closed, which is why a choice showed nothing."""
    assert not _is_open(page)


def test_choosing_an_order_by_radio_opens_the_section(page: Page) -> None:
    """A radio choice shows its effect."""
    page.check("input[name='listmode'][value='newest']")
    assert _is_open(page)


def test_choosing_an_order_by_key_opens_the_section(page: Page) -> None:
    """The 1 to 6 keys do the same."""
    page.keyboard.press("3")
    assert _is_open(page)


def test_choosing_a_clock_opens_the_section(page: Page) -> None:
    """The recent order's clock radios do too."""
    page.check("input[name='listmode'][value='recent']")
    page.locator(f"{SECTION} > summary").click()
    assert not _is_open(page)
    page.check("input[name='listclock'][value='issued']")
    assert _is_open(page)
