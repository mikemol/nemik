# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2260: what the page asks for when a poll tick meets a load, or a piece fails."""

import functools
import http.server
import json
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import webpage
from playwright.sync_api import (
    Browser,
    Page,
    Playwright,
    Request,
    Route,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

from nemik.serve import PageServer, build_static

if TYPE_CHECKING:
    from collections.abc import Iterator

FLEET = Path(__file__).parent / "fixtures" / "fleet"
POLL_MS = 60_000
TWO_LOADS = 2  # the first load and the one the poll tick starts
PIECE = re.compile(r"/graph/(?!_)[^/]+\.json$")
FAILED_AT_FIRST = 10  # how many of the first round's piece requests the server refuses
DATA_DRAWN = "() => typeof data !== 'undefined' && data"
ASKED = "() => [...window.__pieceFetches]"
ATTEMPTS = 2  # the old fetch and the one the moved hash asked for
ONE = "aeternum"  # a repo of the fixture fleet, whose piece the late-failure case moves
KEPT = f"() => Object.keys(pieceCache).some(k => k.endsWith('graph/{ONE}.json'))"
START_LOAD = "() => { load(); }"  # not awaited: the round waits on a held piece
WAITS = 2000  # evaluations a held request may take to reach the route handler


@pytest.fixture()
def served(tmp_path: Path) -> Iterator[str]:
    """Serve a static build of the fixture fleet on a port the server picks.

    Yields:
        The server's address.

    """
    withheld = tmp_path / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(out)
    )
    httpd = PageServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()


def _browser(playwright: Playwright) -> Browser:
    """Launch the staged Chromium, or skip the test when it is unavailable.

    Returns:
        The browser.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        return playwright.chromium.launch(
            executable_path=str(Path(exe).absolute()) if exe else None
        )
    except PlaywrightError as e:
        pytest.skip(f"chromium unavailable: {e}")


def _asked(page: Page) -> list[str]:
    """Read the paths the page fetched, in order.

    Returns:
        The page's __pieceFetches.

    """
    return webpage.as_strs(webpage.evaluate_value(page, ASKED))


def test_a_poll_tick_during_a_load_fetches_no_piece_twice(served: str) -> None:
    """Hold the first load's pieces, let the 60 s poll tick, release: each piece was asked once."""
    held: list[Route] = []
    rounds: list[str] = []

    def hold(route: Route) -> None:
        held.append(route)

    def count(request: Request) -> None:
        if request.url.endswith("/hashes.json"):
            rounds.append(request.url)

    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.clock.install()
        page.route(PIECE, hold)
        page.on("request", count)
        webpage.watch(page)
        page.goto(served)
        webpage.until(page, "() => window.__pieceFetches.length > 1")
        page.clock.run_for(POLL_MS + 1000)
        webpage.until(page, "() => window.__pieceFetches.length > 1")
        for route in held:
            route.continue_()
        webpage.until(page, DATA_DRAWN)
        fetched = _asked(page)
        browser.close()
    assert len(rounds) >= TWO_LOADS, f"the tick started no second load: {rounds}"
    pieces = [f for f in fetched if f != "graph/_fleet.json"]
    assert len(pieces) == len(set(pieces)), f"asked twice: {fetched}"


def test_pieces_the_server_refuses_once_are_asked_again_by_the_next_round(
    served: str,
) -> None:
    """The first round's first FAILED_AT_FIRST piece requests are aborted: the poll retries them."""
    seen: Counter[str] = Counter()

    def refuse_first(route: Route) -> None:
        seen[route.request.url] += 1
        if sum(seen.values()) <= FAILED_AT_FIRST:
            route.abort()
        else:
            route.continue_()

    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.clock.install()
        page.route(PIECE, refuse_first)
        webpage.watch(page)
        page.goto(served)
        webpage.until(page, "() => window.__pieceFetches.length > 1")
        page.clock.run_for(POLL_MS + 1000)
        webpage.until(page, DATA_DRAWN)
        fetched = _asked(page)
        failed = webpage.as_strs(
            webpage.evaluate_value(page, "() => [...window.__pieceFailures]")
        )
        browser.close()
    assert len(failed) == FAILED_AT_FIRST, f"failures recorded: {failed}"
    attempts = Counter(fetched)
    again = {k: n - 1 for k, n in attempts.items() if n > 1}
    assert again == dict(Counter(failed)), f"retries {again} vs failures {failed}"


def _wait_held(page: Page, held: list[Route], count: int) -> None:
    """Let the page run until the route has held `count` requests."""
    for _ in range(WAITS):
        if len(held) >= count:
            return
        webpage.evaluate_value(page, "() => 0")
    pytest.fail(f"only {len(held)} of {count} requests reached the route")


def _move_piece_hash(out: Path) -> None:
    """Change ONE's hash in hashes.json, a second after the first read (Last-Modified)."""
    time.sleep(1.1)
    path = out / "hashes.json"
    text = path.read_text(encoding="utf-8")
    moved = re.sub(rf'("graph/{ONE}\.json":\s*")', r"\1moved-", text)
    path.write_text(moved, encoding="utf-8")


def test_an_old_fetch_failing_late_does_not_drop_the_newer_entry(
    served: str, tmp_path: Path
) -> None:
    """A fetch that fails after its hash moved leaves the newer entry for the next round."""
    held: list[Route] = []

    def hold(route: Route) -> None:
        # only the first two requests for ONE are held: a third (a dropped entry asked for again)
        # is let through, so the case ends red instead of waiting on a held request forever
        if route.request.url.endswith(f"/graph/{ONE}.json") and len(held) < ATTEMPTS:
            held.append(route)
        else:
            route.continue_()

    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page()
        page.route(PIECE, hold)
        webpage.watch(page)
        page.goto(served)
        _wait_held(page, held, 1)
        _move_piece_hash(tmp_path / "out")
        webpage.evaluate_value(page, START_LOAD)
        _wait_held(page, held, ATTEMPTS)
        held[0].abort()
        webpage.until(page, "() => window.__pieceFailures.length > 0")
        kept = webpage.evaluate_value(page, KEPT)
        held[1].continue_()
        webpage.until(page, DATA_DRAWN)
        webpage.evaluate_value(page, "() => load()")
        fetched = _asked(page)
        browser.close()
    assert kept is True, "the old fetch's late failure dropped the newer entry"
    assert fetched.count(f"graph/{ONE}.json") == ATTEMPTS, fetched
