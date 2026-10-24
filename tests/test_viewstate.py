# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W952: the page's address is state: a scope path and a view token, round-tripped."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error, Page, ViewportSize, sync_playwright

VIEWPORT = ViewportSize(width=1700, height=1250)
READY = "() => typeof parseAddress === 'function' && typeof cy !== 'undefined' && cy"
EMPTY = {"scope": [], "view": ""}


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


def _parse(page: Page, address: str) -> object:
    """Parse an address in the page.

    Returns:
        The state the page's parseAddress gives.

    """
    got: object = page.evaluate("a => parseAddress(a)", address)
    return got


def test_an_address_names_a_scope_path_and_a_view(server: str, page: Page) -> None:
    """Fleet, repo, umbrella and card are read from the path, the view from the query."""
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    assert _parse(page, "#/beta/W3/W5?view=queue") == {
        "scope": ["beta", "W3", "W5"],
        "view": "queue",
    }
    assert _parse(page, "#/beta") == {"scope": ["beta"], "view": ""}
    assert _parse(page, "#/") == EMPTY
    assert _parse(page, "") == EMPTY


def test_format_is_the_inverse_of_parse(server: str, page: Page) -> None:
    """Every state formats to an address that parses back to it."""
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    states = [
        {"scope": [], "view": ""},
        {"scope": ["beta"], "view": "graph"},
        {"scope": ["beta", "W3", "W5"], "view": "queue"},
    ]
    for state in states:
        back: object = page.evaluate("s => parseAddress(formatAddress(s))", state)
        assert back == state


def test_a_malformed_address_is_no_state_at_all(server: str, page: Page) -> None:
    """A bad repo, a bad symbol, a bad view and bad escaping each give the empty state."""
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    for bad in (
        "#/be ta/W3",
        "#/beta/card",
        "#/beta/W3?view=Queue",
        "#/beta/%E0%A4%A",
    ):
        assert _parse(page, bad) == EMPTY, bad
