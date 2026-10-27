# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W442: the generated OpenAPI points at published schemas, and the example client works."""

import functools
import http.server
import importlib.util
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from nemik.serve import build_static

ROOT = Path(__file__).resolve().parents[1]
FLEET = Path(__file__).parent / "fixtures" / "fleet"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("static")
    withheld = tmp / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp / "out"
    build_static(FLEET, out, withheld)
    return out


@pytest.fixture(scope="module")
def served(built: Path) -> Iterator[str]:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(built)
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


def _client_module():  # tools/ is not a package: load the example as the reader would run it
    spec = importlib.util.spec_from_file_location(
        "nemik_client", ROOT / "tools" / "nemik_client.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_openapi_ref_is_a_published_schema(built: Path) -> None:
    api = json.loads((built / "openapi.json").read_text())
    assert api["openapi"].startswith("3.1")
    refs = [
        op["get"]["responses"]["200"]["content"]["application/json"]["schema"].get(
            "$ref"
        )
        for op in api["paths"].values()
    ]
    refs = [r for r in refs if r]
    assert refs
    for ref in refs:
        assert (built / ref).exists(), ref


def test_the_example_client_fetches_once_then_only_what_moved(served: str) -> None:
    client = _client_module().Client(served)
    first = client.refresh()
    assert "graph.json" in first and "openapi.json" in first
    assert client.refresh() == []  # nothing moved, nothing fetched
    assert client.docs["graph.json"]["nodes"]
