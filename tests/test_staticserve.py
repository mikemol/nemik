# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W502: the snapshot file server: types, validators, containment, readiness, and no rdflib."""

import hashlib
import http.client
import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from nemik.staticserve import handler, resolve, snapshot


def _publish(root: Path) -> None:
    (root / "graph").mkdir(parents=True)
    (root / "index.html").write_text("<html>view</html>")
    piece = json.dumps({"nodes": []})
    (root / "graph" / "r.json").write_text(piece)
    (root / "catalog.ttl").write_text("# turtle")
    digest = hashlib.sha256(piece.encode()).hexdigest()
    (root / "hashes.json").write_text(json.dumps({"graph/r.json": digest}))


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[Path, int]]:
    root = tmp_path / "pub"
    root.mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(root))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, server.server_address[1]
    server.shutdown()


def _get(
    port: int, path: str, headers: dict[str, str] | None = None, method: str = "GET"
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, headers=headers or {})
    resp = conn.getresponse()
    body = resp.read()
    out = (resp.status, {k.lower(): v for k, v in resp.getheaders()}, body)
    conn.close()
    return out


def test_files_are_served_with_their_types_and_published_validators(
    served: tuple[Path, int],
) -> None:
    root, port = served
    _publish(root)
    status, head, body = _get(port, "/graph/r.json")
    assert (status, head["content-type"], body) == (
        200,
        "application/json",
        b'{"nodes": []}',
    )
    digest = hashlib.sha256(body).hexdigest()
    assert head["etag"] == f'"{digest}"'
    assert _get(port, "/catalog.ttl")[1]["content-type"] == "text/turtle"
    assert _get(port, "/")[2] == b"<html>view</html>"


def test_a_matching_validator_is_answered_without_a_body(
    served: tuple[Path, int],
) -> None:
    root, port = served
    _publish(root)
    tag = _get(port, "/graph/r.json")[1]["etag"]
    status, _, body = _get(port, "/graph/r.json", {"If-None-Match": tag})
    assert (status, body) == (304, b"")
    assert _get(port, "/graph/r.json", {"If-None-Match": '"other"'})[0] == 200
    assert _get(port, "/graph/r.json", method="HEAD")[2] == b""


def test_a_path_cannot_leave_the_snapshot(served: tuple[Path, int]) -> None:
    root, port = served
    _publish(root)
    (root.parent / "secret.txt").write_text("secret")
    (root / "link").symlink_to(root.parent / "secret.txt")
    for path in (
        "/../secret.txt",
        "/%2e%2e/secret.txt",
        "/graph/../../secret.txt",
        "/link",
    ):
        assert _get(port, path)[0] == 404, path
    assert resolve(root, "/graph/%00x") is None


def test_readiness_waits_for_a_snapshot_and_liveness_does_not(
    served: tuple[Path, int],
) -> None:
    root, port = served
    assert _get(port, "/healthz")[0] == 200
    assert _get(port, "/metrics")[0] == 503
    (root / "metrics").write_text("nemik_graph_nodes 3\n")
    status, head, body = _get(port, "/metrics")
    assert (status, body) == (200, b"nemik_graph_nodes 3\n")
    assert head["content-type"] == "text/plain; version=0.0.4"


def test_a_published_current_link_is_what_is_served(served: tuple[Path, int]) -> None:
    root, port = served
    for name in ("snap-1", "snap-2"):
        (root / name).mkdir()
        (root / name / "index.html").write_text(name)
    (root / "current").symlink_to("snap-1")
    assert _get(port, "/")[2] == b"snap-1"
    (root / "next").symlink_to("snap-2")
    (root / "next").replace(root / "current")  # the atomic flip a publisher does
    assert _get(port, "/")[2] == b"snap-2"
    assert snapshot(root) == root / "current"


def test_the_live_servers_extensionless_paths_still_answer(
    served: tuple[Path, int],
) -> None:
    # W503: /wake, /operator, /inbound, /inbound/<repo> and /goals/<repo> were routes of the dynamic
    # server; the snapshot holds them as .json files and the file server maps the old spelling on.
    root, port = served
    (root / "inbound").mkdir()
    (root / "goals").mkdir()
    (root / "wake.json").write_text('{"roster": []}')
    (root / "inbound.json").write_text("[1]")
    (root / "inbound" / "r.json").write_text("[2]")
    (root / "goals" / "r.json").write_text("[3]")
    assert _get(port, "/wake")[2] == b'{"roster": []}'
    assert _get(port, "/inbound")[2] == b"[1]"
    assert _get(port, "/inbound/r")[2] == b"[2]"
    assert _get(port, "/goals/r")[2] == b"[3]"
    assert _get(port, "/inbound/none")[0] == 404


def test_the_server_never_imports_rdflib() -> None:
    probe = "import nemik.staticserve, sys; sys.exit('rdflib' in sys.modules)"
    run = subprocess.run([sys.executable, "-I", "-c", probe], check=False)
    assert run.returncode == 0, "nemik.staticserve pulled in rdflib"
