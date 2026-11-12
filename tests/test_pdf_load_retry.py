# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W846: nemik.pdf opens its page again when the host's network changed under the load.

Playwright cannot produce net::ERR_NETWORK_CHANGED, so the browser, the page and the request are
small fakes that carry the failure text, and nemik.pdf.load is a script of outcomes. The witness is
the construction: a load lost to a network change is tried again on a fresh page, at most
LOAD_TRIES times, and any other failure is not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, cast

import pytest
from mikemol.webpage.page import PageBrokenError
from playwright.sync_api import Browser, ViewportSize

from nemik import pdf

if TYPE_CHECKING:
    from collections.abc import Callable


CHANGED = "net::ERR_NETWORK_CHANGED"
REFUSED = "net::ERR_CONNECTION_REFUSED"
TWO_PAGES = 2


class _Request(NamedTuple):
    url: str
    failure: str


class _Page:
    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[_Request], None]] = {}
        self.closed = False

    def on(self, event: str, handler: Callable[[_Request], None]) -> None:
        self.handlers[event] = handler

    def close(self) -> None:
        self.closed = True


class _Browser:
    def __init__(self) -> None:
        self.pages: list[_Page] = []

    def new_page(self, *, viewport: ViewportSize) -> _Page:
        assert viewport == pdf.VIEWPORT
        page = _Page()
        self.pages.append(page)
        return page


def _script(outcomes: list[str]) -> Callable[[_Page, str, str], None]:
    """Script mikemol.webpage.page.load: each call plays the next outcome.

    Returns:
        The stand-in: "ok" returns, any other text fails one request with it and raises.

    """
    played = iter(outcomes)

    def load(page: _Page, url: str, wait: str) -> None:
        assert wait == pdf.CY_READY
        outcome = next(played)
        if outcome == "ok":
            return
        page.handlers["requestfailed"](_Request(f"{url}cards.js", outcome))
        message = "the page broke while the test waited on it: popLater is not defined"
        raise PageBrokenError(message)

    return load


def test_a_load_lost_to_a_network_change_is_opened_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first load loses every request to a network change; the second page is the result."""
    monkeypatch.setattr(pdf, "load", _script([CHANGED, "ok"]))
    browser = _Browser()
    page = pdf.loaded_page(cast("Browser", browser), "http://x/")
    assert len(browser.pages) == TWO_PAGES
    assert browser.pages[0].closed
    assert cast("object", page) is browser.pages[1]


def test_three_loads_lost_to_a_network_change_raise_with_the_failure_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every try lost: the error after LOAD_TRIES pages names the network-changed text."""
    monkeypatch.setattr(pdf, "load", _script([CHANGED] * pdf.LOAD_TRIES))
    browser = _Browser()
    with pytest.raises(pdf.NetworkChangedError, match=CHANGED):
        pdf.loaded_page(cast("Browser", browser), "http://x/")
    assert len(browser.pages) == pdf.LOAD_TRIES
    assert all(page.closed for page in browser.pages)


def test_another_failure_is_not_tried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refused connection is a real fault: one page, a plain PageBrokenError."""
    monkeypatch.setattr(pdf, "load", _script([REFUSED, "ok"]))
    browser = _Browser()
    with pytest.raises(PageBrokenError, match=REFUSED) as raised:
        pdf.loaded_page(cast("Browser", browser), "http://x/")
    assert not isinstance(raised.value, pdf.NetworkChangedError)
    assert len(browser.pages) == 1
