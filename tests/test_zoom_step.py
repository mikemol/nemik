# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W920: one wheel notch zooms the graph by a small step, not by cytoscape's default 2.5x."""

import webpage
from playwright.sync_api import sync_playwright

NOTCH = 100  # a mouse wheel notch is a deltaY of 100 pixels in Chromium
CENTRE = (600, 600)
LOWEST_STEP = 1.05
HIGHEST_STEP = 1.35


def test_a_wheel_notch_changes_the_zoom_by_a_small_step() -> None:
    """The zoom ratio of one notch in and one notch out is between 5% and 35%."""
    with webpage.served() as url, sync_playwright() as p:
        # nemik:W846: launched_page names the requests that failed if the page breaks on load
        browser, page = webpage.launched_page(p, url)
        try:
            before: object = page.evaluate("() => cy.zoom()")
            page.mouse.move(*CENTRE)
            page.mouse.wheel(0, -NOTCH)
            after_in: object = page.evaluate("() => cy.zoom()")
            page.mouse.wheel(0, NOTCH)
            after_out: object = page.evaluate("() => cy.zoom()")
        finally:
            browser.close()
    assert isinstance(before, float | int)
    assert isinstance(after_in, float | int)
    assert isinstance(after_out, float | int)
    step_in = after_in / before
    step_out = after_in / after_out
    assert LOWEST_STEP < step_in < HIGHEST_STEP, step_in
    assert LOWEST_STEP < step_out < HIGHEST_STEP, step_out
