# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik: a served fixture fleet and a Chromium page on it, for browser tests outside test_layout.

test_layout.py keeps its own server fixture (a large file, edited in one piece); new browser tests
share this one. The waits that end on the page's own event (watch, until, until_expecting, load)
are mtools' mikemol.webpage (nemik:W717, W848), re-exported here so the tests keep one import.
"""

import os
import socket
import subprocess
import tempfile
import time
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
CY_READY = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1"


class Seen(Protocol):
    """What the page's request and response events give that W1060 reads."""

    url: str
    status: int


class Pager(Waitable, Protocol):
    """A page that reports its requests and responses."""

    def on(self, event: str, handler: Callable[[Seen], None]) -> None:
        """Call `handler` on each `event`."""


@contextmanager
def served(series: Path | None = None) -> Iterator[str]:
    """nemik-serve over the fixture fleet, on a free port; yields its URL.

    `series` is luthen's snapshot file, passed as --series when given (nemik:W669).

    Raises:
        RuntimeError: The server never answered; its stderr is in the message (W1060).

    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**installed._bin()[1], "PYTHONHASHSEED": "0"}
    extra = ["--series", str(series)] if series is not None else []
    command = [
        *installed.script("nemik-serve"),
        "--root",
        str(FLEET),
        "--port",
        str(port),
        *extra,
    ]
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=log)
        try:
            for _ in range(100):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                log.seek(0)
                message = (
                    f"nemik-serve never answered on port {port}: {log.read().decode()}"
                )
                raise RuntimeError(message)
            yield f"http://127.0.0.1:{port}/"
        finally:
            proc.terminate()
            proc.wait()


def open_page(p: Any, url: str, wait: str = CY_READY) -> tuple[Any, Any]:
    """A browser and a page on `url`, once `wait` (a JS predicate) holds; skips without a browser.

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

    page.on("requestfailed", note_failed)
    page.on("response", note_status)
    try:
        load(page, url, wait)
    except PageBrokenError as e:
        message = f"{e}; requests refused or failed: {refused}"
        raise PageBrokenError(message) from e
    return browser, page
