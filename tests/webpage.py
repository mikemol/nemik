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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

import installed
import pytest
from mikemol.webpage.page import (
    PageBrokenError,
    Waitable,
    load,
    until,
    until_expecting,
    watch,
)

sync_api = pytest.importorskip("playwright.sync_api")
__all__ = [
    "CY_READY",
    "FLEET",
    "PageBrokenError",
    "Waitable",
    "load",
    "open_page",
    "served",
    "until",
    "until_expecting",
    "watch",
]

FLEET = Path(__file__).parent / "fixtures" / "fleet"
HTTP_ERROR = 400
LISTENING_WORDS = 2  # the server's line is "listening" and a port
CY_READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1"


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


class Browser(Protocol):
    """A launched browser, as far as open_page needs it."""

    def new_page(self, *, viewport: dict[str, int]) -> Pager:
        """Open a page of that size."""


class Chromium(Protocol):
    """Playwright's Chromium launcher."""

    def launch(self, *, executable_path: str | None = None) -> Browser:
        """Start the browser."""


class Playwright(Protocol):
    """What sync_playwright() yields that open_page reads."""

    chromium: Chromium


@contextmanager
def served(series: Path | None = None, root: Path = FLEET) -> Iterator[str]:
    """nemik-serve over `root` (the fixture fleet), on a port it binds itself; yields its URL.

    `series` is luthen's snapshot file, passed as --series when given (nemik:W669).

    The server is started on port 0 and says "listening <port>" once its socket listens (W1060),
    so the port is never picked, closed and hoped for: between a pick and a bind another process
    could take it, and the connect loop that used to follow would have succeeded against that
    process's server.

    Raises:
        RuntimeError: The server did not say it listens; its stderr is in the message.

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
            yield f"http://127.0.0.1:{told[1]}/"
        finally:
            proc.terminate()
            proc.wait()


def open_page(
    p: Playwright, url: str, wait: str = CY_READY, block: tuple[str, ...] = ()
) -> tuple[Any, Any]:
    """A browser and a page on `url`, once `wait` (a JS predicate) holds; skips without a browser.

    `block` names files whose requests are refused, as a server that went away would (W1069).

    Raises:
        PageBrokenError: The page broke; the message lists the requests that failed or got an
            error status, so a script missing under load names the asset (W1060).

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        browser = p.chromium.launch(
            executable_path=os.path.abspath(exe) if exe else None
        )
    except sync_api.Error as e:
        pytest.skip(f"chromium unavailable: {e}")
    page: Pager = browser.new_page(viewport={"width": 1700, "height": 1250})
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


def first_error(block: tuple[str, ...]) -> str:
    """Load the page with the requests for `block` refused and read the error it breaks on.

    Returns:
        The page-broken message, or an empty string when the page loaded.

    """
    with served() as url, sync_api.sync_playwright() as p:
        try:
            open_page(p, url, block=block)
        except PageBrokenError as e:
            return str(e)
    return ""
