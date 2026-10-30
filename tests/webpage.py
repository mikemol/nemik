# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik: a served fixture fleet and a Chromium page on it, for browser tests outside test_layout.

test_layout.py keeps its own server fixture (a large file, edited in one piece); new browser tests
share this one. The waits that end on the page's own event (watch, until, until_expecting, load)
are mtools' mikemol.webpage (nemik:W717, W848), re-exported here so the tests keep one import.
"""

import os
import subprocess
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

import installed
import pytest
from mikemol.webpage.page import (
    PageBrokenError,
    Waitable,
    load,
    until_expecting,
)
from mikemol.webpage.page import until as library_until
from mikemol.webpage.page import watch as library_watch
from playwright.sync_api import Browser as LaunchedBrowser
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page as LaunchedPage
from playwright.sync_api import Playwright as Launcher
from playwright.sync_api import Request as LaunchedRequest
from playwright.sync_api import Response as LaunchedResponse

from nemik.tracker import BOOL, INT, Tree, parse_tree

sync_api = pytest.importorskip("playwright.sync_api")
__all__ = [
    "CY_READY",
    "FLEET",
    "PageBrokenError",
    "Waitable",
    "evaluate_value",
    "evaluated",
    "first_error",
    "launched_page",
    "load",
    "open_page",
    "opened_page",
    "served",
    "until",
    "until_expecting",
    "watch",
]

FLEET = Path(__file__).parent / "fixtures" / "fleet"
HTTP_ERROR = 400
LISTENING_WORDS = 2  # the server's line is "listening" and a port
CY_READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1"
# nemik:W846: records, inside the page, each resource (a script tag, a stylesheet) whose load
# failed. An error event on such an element does not bubble, so the listener is a capture listener
# on the window. It rests on the page alone (no Playwright event), so it works for every page that
# `watch` is called on, whatever type the test holds.
RECORD_FAILED = (
    "window.__failed = [];"
    "window.addEventListener('error', e => {"
    " const t = e.target;"
    " if (t && t !== window && (t.src || t.href)) window.__failed.push(String(t.src || t.href));"
    "}, true);"
)


def watch(page: Waitable) -> None:
    """Install the page's error record and the failed-resource record, before it navigates.

    Args:
        page: The Playwright page.

    """
    library_watch(page)
    page.add_init_script(RECORD_FAILED)


def until(page: Waitable, expr: str) -> None:
    """Wait on a page predicate with no clock; a broken page names the resources that failed.

    Args:
        page: The Playwright page, watched before it navigated.
        expr: A JS arrow function that is truthy once the page is ready.

    Raises:
        PageBrokenError: The page broke; the message lists the resources that failed to load, so
            a script missing under load names the asset (W846, W1060).

    """
    try:
        library_until(page, expr)
    except PageBrokenError as e:
        failed = page.evaluate("() => window.__failed || []")
        message = f"{e}; resources that failed to load: {failed}"
        raise PageBrokenError(message) from e


class Seen(Protocol):
    """What the page's request and response events give that W1060 reads."""

    url: str
    status: int


class Route(Protocol):
    """A request the page has paused for a handler."""

    def abort(self) -> None:
        """Fail the request as a refused connection would."""


class Pager(Waitable, Protocol):
    """A page that reports its requests and responses."""

    def on(self, event: str, handler: Callable[[Seen], None]) -> None:
        """Call `handler` on each `event`."""

    def route(self, pattern: str, handler: Callable[[Route], None]) -> None:
        """Call `handler` on each request whose URL matches `pattern`."""

    def evaluate(self, expression: str) -> object:
        """Run the JS expression in the page and return its value, a promise awaited."""

    def inner_text(self, selector: str) -> str:
        """Give the text of the first element matching `selector`."""


class Browser(Protocol):
    """A launched browser, as far as open_page needs it."""

    def new_page(self, *, viewport: dict[str, int]) -> Pager:
        """Open a page of that size."""

    def close(self) -> None:
        """Shut the browser."""


class Chromium(Protocol):
    """Playwright's Chromium launcher."""

    def launch(self, *, executable_path: str | None = None) -> Browser:
        """Start the browser."""


class Playwright(Protocol):
    """What sync_playwright() yields that open_page reads."""

    chromium: Chromium


@contextmanager
def served(series: Path | None = None, root: Path = FLEET) -> Generator[str]:
    """nemik-serve over `root` (the fixture fleet), on a port it binds itself; yields its URL.

    `series` is luthen's snapshot file, passed as --series when given (nemik:W669).

    The server is started on port 0 and says "listening <port>" once its socket listens (W1060),
    so the port is never picked, closed and hoped for: between a pick and a bind another process
    could take it, and the connect loop that used to follow would have succeeded against that
    process's server.

    Raises:
        RuntimeError: The server did not say it listens; its stderr is in the message.
        PageBrokenError: A page broke inside the block; the message adds whether the server still
            ran and the tail of its stderr (W846).

    """
    env = {**installed._bin()[1], "PYTHONHASHSEED": "0"}
    extra = ["--series", str(series)] if series is not None else []
    command = [
        *installed.script("nemik-serve"),
        "--root",
        str(root),
        "--port",
        "0",
        *extra,
    ]
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=log)
        try:
            told = proc.stdout.readline().decode().split() if proc.stdout else []
            if len(told) != LISTENING_WORDS or told[0] != "listening":
                log.seek(0)
                message = (
                    f"nemik-serve did not say it listens: {told}: {log.read().decode()}"
                )
                raise RuntimeError(message)
            try:
                yield f"http://127.0.0.1:{told[1]}/"
            except PageBrokenError as e:
                # nemik:W846: five scripts failed at once under the gate, which points at the
                # server, so a broken page says whether nemik-serve still ran and what it wrote.
                log.seek(0)
                message = (
                    f"{e}; nemik-serve alive: {proc.poll() is None}; "
                    f"its stderr: {log.read().decode()[-2000:]}"
                )
                raise PageBrokenError(message) from e
        finally:
            proc.terminate()
            proc.wait()


def opened_page(
    p: Playwright, url: str, wait: str = CY_READY, block: tuple[str, ...] = ()
) -> tuple[Browser, Pager]:
    """A browser and a page on `url`, once `wait` (a JS predicate) holds; skips without a browser.

    `block` names files whose requests are refused, as a server that went away would (W1069).

    Raises:
        PageBrokenError: The page broke; the message lists the requests that failed or got an
            error status, so a script missing under load names the asset (W1060).

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        browser = p.chromium.launch(
            executable_path=str(Path(exe).absolute()) if exe else None
        )
    except PlaywrightError as e:
        pytest.skip(f"chromium unavailable: {e}")
    page = browser.new_page(viewport={"width": 1700, "height": 1250})
    refused: list[str] = []

    def note_failed(request: Seen) -> None:
        refused.append(f"failed {request.url}")

    def note_status(response: Seen) -> None:
        if response.status >= HTTP_ERROR:
            refused.append(f"{response.status} {response.url}")

    def refuse(route: Route) -> None:
        route.abort()

    for name in block:
        page.route(f"**/{name}", refuse)
    page.on("requestfailed", note_failed)
    page.on("response", note_status)
    try:
        load(page, url, wait)
    except PageBrokenError as e:
        message = f"{e}; requests refused or failed: {refused}"
        raise PageBrokenError(message) from e
    return browser, page


def open_page(
    p: Playwright, url: str, wait: str = CY_READY, block: tuple[str, ...] = ()
) -> tuple[Any, Any]:
    """Open the page as opened_page does, for the tests that drive it with Playwright's own API.

    Returns:
        The browser and the page, untyped: a test moves to opened_page (typed by the Protocols
        above) as it is converted (nemik:W1177).

    """
    return opened_page(p, url, wait, block)


def launched_page(
    p: Launcher,
    url: str,
    wait: str = CY_READY,
    viewport: tuple[int, int] = (1700, 1250),
) -> tuple[LaunchedBrowser, LaunchedPage]:
    """Launch Chromium with the library's own types and open `url` once `wait` holds (nemik:W1177).

    The typed route for a test that drives Playwright's API itself: unlike open_page it returns
    the library's Browser and Page, so nothing is Any except what the page's evaluate answers (read
    that through evaluate_value). A pinned headless shell in $NEMIK_CHROMIUM is used when set.

    Returns:
        The browser and the page, once the predicate holds; skips without a browser.

    Raises:
        PageBrokenError: The page broke; the message lists the requests that failed or got an
            error status, so a script missing under load names the asset (W846, W1060).

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        browser = p.chromium.launch(
            executable_path=str(Path(exe).absolute()) if exe else None
        )
    except PlaywrightError as e:
        pytest.skip(f"chromium unavailable: {e}")
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
    refused: list[str] = []

    def note_failed(request: LaunchedRequest) -> None:
        # nemik:W846: the error text says why (net::ERR_CONNECTION_RESET, ...), not only which URL
        refused.append(f"failed {request.url} ({request.failure})")

    def note_status(response: LaunchedResponse) -> None:
        if response.status >= HTTP_ERROR:
            refused.append(f"{response.status} {response.url}")

    page.on("requestfailed", note_failed)
    page.on("response", note_status)
    try:
        load(page, url, wait)
    except PageBrokenError as e:
        message = f"{e}; requests refused or failed: {refused}"
        raise PageBrokenError(message) from e
    return browser, page


@contextmanager
def session(block: tuple[str, ...] = ()) -> Generator[Pager]:
    """Serve the fixture fleet, open the page on it and yield the page (nemik:W975).

    A page that breaks while loading, with `block` refused, raises PageBrokenError.

    Yields:
        The page, once its predicate holds.

    """
    with served() as url, sync_api.sync_playwright() as p:
        yield opened_page(p, url, block=block)[1]


class Evaluator(Protocol):
    """Anything that runs a JS expression: Playwright's page, whose own answer is Any."""

    def evaluate(self, expression: str, arg: object = None) -> object:
        """Run the JS expression in the page, passing `arg`, and return its value."""


def evaluate_value(page: Evaluator, expression: str, arg: object = None) -> object:
    """Run a JS expression in a page and return its value as an object, never as Any.

    Playwright's Page.evaluate answers Any, which the house type check counts at every call.
    Reading it through this protocol types the answer as object once, so a test narrows it with
    isinstance where it needs a number or a string (nemik:W1177).

    Returns:
        The expression's value, as the browser serialised it.

    """
    return page.evaluate(expression, arg)


def evaluate_text(page: Evaluator, expression: str, arg: object = None) -> str:
    """Run a JS function in a page and return what it gave as JSON text.

    The page does the serialising (JSON.stringify of the awaited result), so a test compares two
    answers as strings or reads one through nemik.tracker, with no dict or list of Any between.

    Returns:
        The JSON text of the function's result.

    Raises:
        TypeError: When the function gave nothing JSON can carry (undefined).

    """
    wrapped = (
        f"(arg) => Promise.resolve(({expression})(arg)).then(v => JSON.stringify(v))"
    )
    value = page.evaluate(wrapped, arg)
    if not isinstance(value, str):
        message = f"{expression[:60]!r} gave no JSON, only {value!r}"
        raise TypeError(message)
    return value


def evaluate_tree(page: Evaluator, expression: str, arg: object = None) -> Tree:
    """Run a JS function in a page and parse what it gave into a tree.

    Returns:
        The parsed result; read it with flag, whole and tree.string.

    """
    return parse_tree(evaluate_text(page, expression, arg))


def flag(tree: Tree, key: str) -> bool:
    """Read a boolean member of the tree's root object.

    Returns:
        True only when the member is the boolean true; absent or any other kind reads False.

    """
    at = tree.get(tree.root, key)
    return tree.kinds[at] == BOOL and tree.flags[at]


def whole(tree: Tree, key: str) -> int:
    """Read an integer member of the tree's root object.

    Returns:
        The integer, or -1 when the member is absent or not an integer.

    """
    at = tree.get(tree.root, key)
    return tree.wholes[at] if tree.kinds[at] == INT else -1


def evaluated(expr: str) -> object:
    """Load the page and return what the JS expression `expr` gives in it.

    Returns:
        The expression's value (a promise is awaited), as the browser serialised it.

    """
    with session() as page:
        return page.evaluate(expr)


def first_error(block: tuple[str, ...]) -> str:
    """Load the page with the requests for `block` refused and read the error it breaks on.

    Returns:
        The page-broken message, or an empty string when the page loaded.

    """
    try:
        with session(block):
            return ""
    except PageBrokenError as e:
        return str(e)
