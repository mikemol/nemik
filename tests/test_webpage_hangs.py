# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W715: a test that waits on a page with no clock still ends when the page breaks."""

import os
from pathlib import Path
from urllib.parse import quote

import pytest
import webpage
from playwright.sync_api import Browser, Page, Route, sync_playwright
from playwright.sync_api import Error as PlaywrightError

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


def test_a_script_that_did_not_load_is_named_when_the_page_breaks() -> None:
    """W846: the first script is lost, the second uses it; the error names the lost asset."""
    lost = (
        '<script src="http://127.0.0.1:1/lost.js"></script><script>usesLost();</script>'
    )
    with pytest.raises(webpage.PageBrokenError, match=r"usesLost.*lost\.js"):
        _serve(lost)


def test_a_broken_page_under_served_says_whether_the_server_still_ran() -> None:
    """W846: the page broke while nemik-serve served it, so the error reports the server's state."""

    def break_under_served() -> None:
        with webpage.served():
            message = "boom"
            raise webpage.PageBrokenError(message)

    with pytest.raises(webpage.PageBrokenError, match=r"boom; nemik-serve alive: True"):
        break_under_served()


def test_a_failed_request_names_the_network_error_text() -> None:
    """W846: launched_page says why a request failed (the network error), not only which one."""
    lost = (
        '<script src="http://127.0.0.1:1/lost.js"></script><script>usesLost();</script>'
    )
    named = r"failed http://127\.0\.0\.1:1/lost\.js \(net::ERR_[A-Z_]+\)"
    with sync_playwright() as p, pytest.raises(webpage.PageBrokenError, match=named):
        webpage.launched_page(p, "data:text/html," + quote(lost))


def test_only_requests_that_died_of_a_network_change_count_as_lost_to_one() -> None:
    """W846: a load is retried only when every failed request says the network changed."""
    changed = f"failed http://h/a.js ({webpage.NETWORK_CHANGED})"
    assert webpage.lost_to_a_network_change([changed, changed])
    assert not webpage.lost_to_a_network_change([])
    assert not webpage.lost_to_a_network_change([changed, "404 http://h/b.js"])
    assert not webpage.lost_to_a_network_change(
        ["failed http://h/c.js (net::ERR_ABORTED)"]
    )


def test_a_load_lost_to_a_network_change_is_opened_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """W846: the first load reports a network change, so launched_page opens a fresh page."""
    real = webpage.first_load
    calls: list[str] = []

    def flaky(
        browser: Browser, url: str, wait: str, viewport: tuple[int, int]
    ) -> tuple[Page, list[str], webpage.PageBrokenError | None]:
        page, refused, broke = real(browser, url, wait, viewport)
        calls.append(url)
        if len(calls) == 1:
            lost = f"failed {url} ({webpage.NETWORK_CHANGED})"
            return page, [lost], webpage.PageBrokenError("the network changed")
        return page, refused, broke

    monkeypatch.setattr(webpage, "first_load", flaky)
    url = "data:text/html," + quote(READIES)
    with sync_playwright() as p:
        browser, _ = webpage.launched_page(p, url, wait=READY)
        browser.close()
    assert calls == [url] * 2


def test_a_script_lost_once_is_loaded_again_by_the_wait() -> None:
    """W846: the first request for the script fails, the second succeeds, and the wait returns."""
    asked: list[str] = []

    def lose_the_first(route: Route) -> None:
        asked.append(route.request.url)
        if len(asked) == 1:
            route.abort()
        else:
            route.fulfill(
                body="window.lib = {ok: true};", content_type="text/javascript"
            )

    html = (
        '<script src="http://nemik.invalid/ready.js"></script>'
        "<script>window.ready = lib.ok;</script>"
    )
    exe = os.environ.get("NEMIK_CHROMIUM")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=str(Path(exe).absolute()) if exe else None
            )
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.route("**/ready.js", lose_the_first)
        webpage.watch(page)
        page.goto("data:text/html," + quote(html))
        webpage.until(page, READY)
        browser.close()
    assert len(asked) > 1


def test_an_unwatched_page_rests_on_its_predicate_alone() -> None:
    """With no error record the wait still ends when the page is ready, and returns no error."""
    assert _serve(READIES, expecting=True, watched=False) is None
