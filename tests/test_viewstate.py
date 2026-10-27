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
        opened = browser.new_page(viewport=VIEWPORT)
        webpage.watch(opened)
        yield opened
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
    webpage.until(page, READY)
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
    webpage.until(page, READY)
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
    webpage.until(page, READY)
    for bad in (
        "#/be ta/W3",
        "#/beta/card",
        "#/beta/W3?view=Queue",
        "#/beta/%E0%A4%A",
    ):
        assert _parse(page, bad) == EMPTY, bad


def _first_card(page: Page) -> tuple[str, str, str]:
    """Name one card of the page's graph.

    Returns:
        Its repo, its symbol and its cite.

    """
    raw: object = page.evaluate(
        "() => { const n = data.nodes.find(n => n.symbol && n.cite);"
        " return [n.repo, n.symbol, n.cite].join(' '); }"
    )
    assert isinstance(raw, str)
    repo, symbol, cite = raw.split(" ")
    return repo, symbol, cite


def test_the_address_picks_the_repo_and_selects_the_card(
    server: str, page: Page
) -> None:
    """Opening an address picks its repo and shows its card in the Selected panel."""
    page.goto(server)
    webpage.until(page, READY)
    repo, symbol, cite = _first_card(page)
    page.goto("about:blank")
    page.goto(f"{server}#/{repo}/{symbol}")
    webpage.until(page, READY)
    page.wait_for_function(
        "c => document.getElementById('detail').textContent.includes(c)", arg=cite
    )
    picked: object = page.evaluate("() => [...picked]")
    assert picked == [repo]


def test_the_address_follows_the_pick_and_the_card_and_back_is_the_way_up(
    server: str, page: Page
) -> None:
    """A repo toggle writes #/repo, a card #/repo/W<n>, and Back returns to the repo's address."""
    page.goto(server)
    webpage.until(page, READY)
    repo, symbol, cite = _first_card(page)
    page.locator(f'#repos button[data-repo="{repo}"]').click()
    page.wait_for_function("h => location.hash === h", arg=f"#/{repo}")
    page.evaluate("c => focusCite(c)", cite)
    page.wait_for_function("h => location.hash === h", arg=f"#/{repo}/{symbol}")
    page.go_back()
    webpage.until(page, READY)
    page.wait_for_function("h => location.hash === h", arg=f"#/{repo}")
    picked: object = page.evaluate("() => [...picked]")
    assert picked == [repo]
    shown = page.locator("#detail").text_content() or ""
    assert cite not in shown


def test_opening_the_page_with_no_address_writes_none(server: str, page: Page) -> None:
    """A page opened bare stays bare: loading is not a navigation."""
    page.goto(server)
    webpage.until(page, READY)
    hash_now: object = page.evaluate("() => location.hash")
    assert not hash_now


def test_an_address_naming_nothing_the_graph_holds_is_ignored(
    server: str, page: Page
) -> None:
    """An unknown repo picks nothing and breaks nothing: every repo stays shown."""
    page.goto(f"{server}#/no-such-repo/W1")
    webpage.until(page, READY)
    picked: object = page.evaluate("() => [...picked]")
    assert picked == []
