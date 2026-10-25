# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1032: vm_export reads the store's raw export and refuses with OSError otherwise."""

import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from nemik.endpoint import vm_export

BODY = '{"metric":{"repo":"a","ratchet":"x"},"values":[1],"timestamps":[2]}\n'
SELECTOR = '{__name__="mikemol.ratchet.value"}'


def _checkout(root: Path, port: int) -> None:
    """Lay down a luthen checkout whose endpoints_query names a local port as the store.

    Args:
        root: The directory that holds the checkout.
        port: The port the fake store listens on.

    """
    package = root / "luthen-observability" / "checks"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    answer = f'{{"state": "answered", "address": "127.0.0.1:{port}"}}'
    (package / "endpoints_query.py").write_text(
        f"print('{answer}')\n", encoding="utf-8"
    )


def _serve(status: HTTPStatus, requests: list[str]) -> HTTPServer:
    """Answer one request on a free local port, recording its request line.

    Args:
        status: The status to answer with.
        requests: Where the request line is appended.

    Returns:
        The server, whose port the caller reads.

    """

    class Answer(BaseHTTPRequestHandler):
        """One canned answer."""

        def do_GET(self) -> None:  # the name http.server dispatches on
            """Record the request and send the body with the chosen status."""
            requests.append(self.path)
            self.send_response(status)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY.encode("utf-8"))

    server = HTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.handle_request, daemon=True).start()
    return server


def test_the_export_is_the_stores_body_asked_for_by_selector_and_start(
    tmp_path: Path,
) -> None:
    """The text comes back whole, and the request names the selector and a relative start."""
    requests: list[str] = []
    server = _serve(HTTPStatus.OK, requests)
    _checkout(tmp_path, server.server_port)
    assert vm_export(SELECTOR, tmp_path) == BODY
    server.server_close()
    assert requests[0].startswith("/api/v1/export?match%5B%5D=")
    assert "start=-30d" in requests[0]


def test_a_store_that_answers_an_error_raises(tmp_path: Path) -> None:
    """A 500 is an OSError naming the status, not an empty export."""
    server = _serve(HTTPStatus.INTERNAL_SERVER_ERROR, [])
    _checkout(tmp_path, server.server_port)
    with pytest.raises(OSError, match="answered 500"):
        vm_export(SELECTOR, tmp_path)
    server.server_close()


def test_a_missing_luthen_checkout_raises(tmp_path: Path) -> None:
    """No checkout, no address for the store."""
    with pytest.raises(OSError, match="vmsingle-http"):
        vm_export(SELECTOR, tmp_path)
