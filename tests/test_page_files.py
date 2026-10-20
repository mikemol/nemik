# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W801: the page's own files beside index.html are served and published when listed.

nemik:W799 splits index.html by concern into a stylesheet and script modules. They are listed in
serve.PAGE_FILES, served by the live server at their names and copied by the static build, when the
file exists; an unlisted file is never served.
"""

import http.client
import shutil
import threading
from http.server import ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

import pytest

from nemik import serve
from nemik.serve import PAGE_FILES, Model, handler, page_file, write_static

PROBE = "style.css"
BODY = b"body { margin: 0; }\n"


@pytest.fixture()
def web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy the package's web directory, add a probe file, and point the server at the copy.

    Returns:
        The copy.

    """
    copy = tmp_path / "web"
    shutil.copytree(Path(str(files("nemik.web"))), copy)
    (copy / PROBE).write_bytes(BODY)
    (copy / "other.css").write_bytes(b"x")

    def here(_name: str) -> Path:
        return copy

    monkeypatch.setattr(serve, "files", here)
    return copy


def test_a_listed_file_that_exists_is_read(web: Path) -> None:
    """The bytes come back, whether the directory is given or the package's own."""
    assert page_file(PROBE, web) == BODY
    assert page_file(PROBE) == BODY


def test_an_unlisted_file_is_never_read(web: Path) -> None:
    """A file in the directory that nobody listed is not served."""
    assert page_file("other.css", web) is None
    assert page_file("../index.html", web) is None


def test_a_listed_file_not_there_yet_is_none(tmp_path: Path) -> None:
    """The names are listed before the files land."""
    assert page_file("graph.js", tmp_path) is None


def test_the_live_server_answers_a_listed_file_with_its_type(
    web: Path, tmp_path: Path
) -> None:
    """GET /style.css is the file, as text/css."""
    del web
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Model(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = int(httpd.server_address[1])
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        connection.request("GET", f"/{PROBE}")
        reply = connection.getresponse()
        got = (reply.status, reply.getheader("Content-Type"), reply.read())
        connection.close()
    finally:
        httpd.shutdown()
    assert got == (200, PAGE_FILES[PROBE], BODY)


def test_the_static_build_copies_the_listed_files_that_exist(
    web: Path, tmp_path: Path
) -> None:
    """The published page has the stylesheet beside index.html, and only what exists."""
    del web
    out = tmp_path / "out"
    out.mkdir()
    written = {path.name for path in write_static(out)}
    assert PROBE in written
    assert (out / PROBE).read_bytes() == BODY
    assert "graph.js" not in written
    assert not (out / "other.css").exists()
