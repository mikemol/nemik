# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W932 (W931): the page's Queue section reads a repo's cards as a numbered queue."""

import json
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
NO_QUEUE = 404


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


def _rows(repo: str) -> dict[str, object]:
    """Build a queue document for `repo` with an older card passed by a newer one.

    Returns:
        A /queue.json document holding two ready cards.

    """
    first = {
        "place": 1,
        "cite": f"{repo}:W901",
        "title": "the newer card",
        "weight": 7,
        "band": "unblock",
        "waited_days": 0.5,
        "overtaken_by": 0,
    }
    second = {
        "place": 2,
        "cite": f"{repo}:W902",
        "title": "the older card",
        "weight": 1,
        "band": "sweep",
        "waited_days": 4.0,
        "overtaken_by": 1,
    }
    return {"as_of": "2026-10-23T00:00:00Z", "queues": {repo: [first, second]}}


def _answer(body: str, status: int) -> Callable[[Route], None]:
    """Make a route handler that answers /queue.json.

    Returns:
        The handler.

    """

    def handler(route: Route) -> None:
        route.fulfill(status=status, content_type="application/json", body=body)

    return handler


def _pick(page: Page) -> str:
    """Toggle the first repo chip.

    Returns:
        The repo it names.

    """
    chip = page.locator("#repos button").first
    repo = chip.get_attribute("data-repo") or ""
    chip.click()
    return repo


def test_a_picked_repo_reads_as_a_numbered_queue(server: str, page: Page) -> None:
    """Places run from 1, each row says why: its weight, its wait and who passed it."""
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    repo = page.locator("#repos button").first.get_attribute("data-repo") or ""
    page.route("**/queue.json", _answer(json.dumps(_rows(repo)), 200))
    page.reload()
    page.wait_for_function(READY, timeout=0)
    _pick(page)
    rows = page.locator("#queue ol.queue").last.locator("li")
    expect(rows).to_have_count(2)
    assert [r.get_attribute("value") for r in rows.all()] == ["1", "2"]
    first, second = (r.text_content() or "" for r in rows.all())
    assert "no newer card ahead of it" in first
    assert "waited 4 days; 1 newer card ranked ahead of it" in second


def test_a_view_without_the_order_says_so(server: str, page: Page) -> None:
    """With no queue.json the section says no order is published, and draws none."""
    page.route("**/queue.json", _answer("{}", NO_QUEUE))
    page.goto(server)
    page.wait_for_function(READY, timeout=0)
    _pick(page)
    expect(page.locator("#queue")).to_contain_text("publishes no queue order")
    expect(page.locator("#queue ol.queue")).to_have_count(0)
