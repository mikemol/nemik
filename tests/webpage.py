# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik: a served fixture fleet and a Chromium page on it, for browser tests outside test_layout.

test_layout.py keeps its own server fixture (a large file, edited in one piece); new browser tests
share this one.
"""

import os
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

import installed
import pytest

sync_api = pytest.importorskip("playwright.sync_api")


class Waitable(Protocol):
    """What `watch` and `until` use of a Playwright page, so they need no Any (nemik:W715)."""

    def add_init_script(self, script: str) -> object:
        """Run `script` in every document the page loads."""

    def wait_for_function(self, expression: str, *, timeout: float) -> object:
        """Wait for a JS predicate to hold."""

    def evaluate(self, expression: str) -> object:
        """Evaluate a JS expression in the page."""


FLEET = Path(__file__).parent / "fixtures" / "fleet"
CY_READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1"


@contextmanager
def served(series: Path | None = None) -> Iterator[str]:
    """nemik-serve over the fixture fleet, on a free port; yields its URL.

    `series` is luthen's snapshot file, passed as --series when given (nemik:W669).
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**installed._bin()[1], "PYTHONHASHSEED": "0"}
    extra = ["--series", str(series)] if series is not None else []
    proc = subprocess.Popen(
        [
            *installed.script("nemik-serve"),
            "--root",
            str(FLEET),
            "--port",
            str(port),
            *extra,
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        proc.terminate()
        proc.wait()


def open_page(p: Any, url: str, wait: str = CY_READY) -> tuple[Any, Any]:
    """A browser and a page on `url`, once `wait` (a JS predicate) holds; skips without a browser."""
    exe = os.environ.get("NEMIK_CHROMIUM")
    try:
        browser = p.chromium.launch(
            executable_path=os.path.abspath(exe) if exe else None
        )
    except sync_api.Error as e:
        pytest.skip(f"chromium unavailable: {e}")
    page = browser.new_page(viewport={"width": 1700, "height": 1250})
    page.goto(url)
    page.wait_for_function(wait, timeout=0)
    return browser, page


# nemik:W715: a wait with no clock needs a way out that is not one. This script, installed before
# the page loads, records the first window error or unhandled rejection; `until` waits on the
# page's own predicate OR that record, so a page that breaks ends the wait with its message
# instead of hanging until the harness kills the target. (A handler that raises does not abort a
# pending wait: probed 2026-10-18, the exception resurfaced at the next call.)
WATCH = (
    "window.__broken = null;"
    "window.addEventListener('error', e => "
    "{ window.__broken = window.__broken || String(e.message); });"
    "window.addEventListener('unhandledrejection', e => "
    "{ window.__broken = window.__broken || String(e.reason); });"
)


class PageBrokenError(AssertionError):
    """The page raised an error or an unhandled rejection while a test waited on it."""


def watch(page: Waitable) -> None:
    """Install the error record on a page; call it before the page navigates.

    Args:
        page: The Playwright page.

    """
    page.add_init_script(WATCH)


def until(page: Waitable, expr: str) -> None:
    """Wait for a page predicate with no clock, or fail with the page's own error.

    Args:
        page: The Playwright page, watched before it navigated.
        expr: A JS arrow function that is truthy once the page is ready.

    Raises:
        PageBrokenError: The page raised an error or unhandled rejection before the predicate held.

    """
    page.wait_for_function(f"() => window.__broken !== null || ({expr})()", timeout=0)
    broken = page.evaluate("() => window.__broken")
    if broken is not None:
        message = f"the page broke while the test waited on it: {broken}"
        raise PageBrokenError(message)
