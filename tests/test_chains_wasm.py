# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W820: the committed chains.wasm is the one its hash names, and the server serves it."""

import hashlib
import http.client
import threading
from http.server import ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from nemik.serve import PAGE_FILES, Model, handler

WEB = Path(str(files("nemik.web")))
MAGIC = b"\0asm"


def test_the_committed_module_matches_its_hash() -> None:
    """tools/build_wasm.sh made it; a hand edit or a stale rebuild changes the hash."""
    named, _, name = (WEB / "chains.wasm.sha256").read_text().strip().partition("  ")
    assert name == "chains.wasm"
    assert hashlib.sha256((WEB / "chains.wasm").read_bytes()).hexdigest() == named


def test_the_module_is_a_wasm_binary() -> None:
    """It starts with the wasm magic number."""
    assert (WEB / "chains.wasm").read_bytes()[:4] == MAGIC


def test_the_server_answers_it_as_application_wasm(tmp_path: Path) -> None:
    """GET /chains.wasm is the file's bytes under the wasm media type the browser needs."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Model(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = int(httpd.server_address[1])
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        connection.request("GET", "/chains.wasm")
        reply = connection.getresponse()
        got = (reply.status, reply.getheader("Content-Type"), reply.read())
        connection.close()
    finally:
        httpd.shutdown()
    assert got == (200, PAGE_FILES["chains.wasm"], (WEB / "chains.wasm").read_bytes())
