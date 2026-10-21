# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W751: the page draws each repo's commit gate times when the host left a landings file."""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import (
    Error,
    Page,
    Route,
    ViewportSize,
    expect,
    sync_playwright,
)

VIEWPORT = ViewportSize(width=1700, height=1250)
READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0"
BOARD = (
    '{"host": true, "as_of": "2026-10-21T06:00:00Z", "stale": false, '
    '"series": {"nemik": [692, 487, 600], "mtools": [938]}, "landings": []}'
)
NO_BOARD = '{"host": false, "why": "no --landings file"}'


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """Serve the fixture fleet.

    Yields:
        The page's URL.

    """
    with webpage.served() as url:
        yield url


@pytest.fixture()
def page() -> Iterator[Page]:
    """Open a browser page, not yet on the server.

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
        yield browser.new_page(viewport=VIEWPORT)
        browser.close()


def _answer(body: str) -> Callable[[Route], None]:
    """Make a route handler that answers /landings.json with `body`.

    Returns:
        The handler.

    """

    def handler(route: Route) -> None:
        route.fulfill(status=200, content_type="application/json", body=body)

    return handler


def test_a_host_board_is_drawn_per_repo(server: str, page: Page) -> None:
    """Each repo's count, median and last gate and a sparkline appear under the wake panel."""
    page.route("**/landings.json", _answer(BOARD))
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    wake = page.locator("#wake")
    expect(wake).to_contain_text("Commit gate times", use_inner_text=False)
    text = wake.text_content() or ""
    assert "3 landed; gate median 10 min, last 10 min" in text
    assert "1 landed; gate median 16 min, last 16 min" in text


def test_no_host_board_draws_nothing(server: str, page: Page) -> None:
    """With host false the wake panel carries no gate-time section."""
    page.route("**/landings.json", _answer(NO_BOARD))
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    expect(page.locator("#wake")).not_to_contain_text(
        "Commit gate times", use_inner_text=False
    )
