# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W822: the page's longest chain is the Python core's, run as wasm in the browser.

The page computes its chains with core.wasm, src/nemik/core/chains.py compiled by Codon, the code
nemik-critical runs natively (goal W812). The legend says how long the view's longest chain is; here
it must equal what Python computes over the same fleet. And a browser that cannot load the module
says so and draws no chain marks: there is no JS copy (nemik:W814).
"""

import os
import re
from collections.abc import Iterator
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

from nemik.critical import critical
from nemik.serve import Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"
VIEWPORT = ViewportSize(width=1700, height=1250)
READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0"
LEGEND = re.compile(r"longest chain, this view \((\d+) cards")


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


def _refuse(route: Route) -> None:
    """Answer a request with a failure, as a browser that cannot fetch the module would see."""
    route.abort()


def test_the_legend_length_is_the_python_cores(server: str, page: Page) -> None:
    """The view's longest chain, drawn from wasm, is critical()'s over the same fleet."""
    model = Model(FLEET)
    model.refresh()
    expected = critical(model.graph).length
    webpage.watch(page)
    page.goto(server)
    webpage.until(page, READY)
    legend = page.locator("#pathkey")
    expect(legend).to_contain_text("longest chain, this view (")
    found = LEGEND.search(legend.inner_text())
    assert found is not None
    assert int(found.group(1)) == expected


def test_a_browser_without_the_module_says_so_and_marks_no_chain(
    server: str, page: Page
) -> None:
    """With core.wasm unfetchable the page tells the viewer and does not draw a chain."""
    page.route("**/core.wasm", _refuse)
    webpage.watch(page)
    page.goto(server)
    webpage.until(page, READY)
    expect(page.locator("#chainsoff")).to_be_visible()
    expect(page.locator("#chainsoff")).to_contain_text("longest-chain marks are off")
    assert LEGEND.search(page.locator("#pathkey").inner_text()) is None
