# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W442: the generated OpenAPI points at published schemas, and the example client works."""

import functools
import http.server
import importlib.util
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict

import pytest

from nemik.serve import build_static

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
FLEET = Path(__file__).parent / "fixtures" / "fleet"

_Media = dict[str, dict[str, str]]
_Content = dict[str, _Media]
_Response = dict[str, _Content]
_Responses = dict[str, _Response]
_Get = dict[str, _Responses]
_Op = dict[str, _Get]


class _Api(TypedDict):
    """The parts of the generated OpenAPI document this test reads."""

    openapi: str
    paths: dict[str, _Op]


class _Client(Protocol):
    """The example client's surface this test uses."""

    docs: dict[str, dict[str, object]]

    def refresh(self) -> list[str]:
        """Fetch what moved."""
        ...


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the static view once for the module.

    Returns:
        The directory it was built into.

    """
    tmp = tmp_path_factory.mktemp("static")
    withheld = tmp / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(payload))
    out = tmp / "out"
    build_static(FLEET, out, withheld)
    return out


@pytest.fixture(scope="module")
def served(built: Path) -> Iterator[str]:
    """Serve the built directory from a local HTTP server.

    Yields:
        The server's base URL.

    """
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(built)
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


def _client_module() -> (
    ModuleType
):  # tools/ is not a package: load the example as the reader would run it
    spec = importlib.util.spec_from_file_location(
        "nemik_client", ROOT / "tools" / "nemik_client.py"
    )
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client_class() -> Callable[[str], _Client]:
    """Load the example client's class.

    Returns:
        The class, called with the base URL.

    """
    cls: Callable[[str], _Client] = _client_module().Client
    return cls


def test_every_openapi_ref_is_a_published_schema(built: Path) -> None:
    """Every openapi ref is a published schema."""
    api: _Api = json.loads((built / "openapi.json").read_text())
    assert api["openapi"].startswith("3.1")
    found = [
        op["get"]["responses"]["200"]["content"]["application/json"]["schema"].get(
            "$ref"
        )
        for op in api["paths"].values()
    ]
    refs = [r for r in found if r]
    assert refs
    for ref in refs:
        assert (built / ref).exists(), ref


def test_the_example_client_fetches_once_then_only_what_moved(served: str) -> None:
    """The example client fetches once then only what moved."""
    client = _client_class()(served)
    first = client.refresh()
    assert "graph.json" in first
    assert "openapi.json" in first
    assert client.refresh() == []  # nothing moved, nothing fetched
    assert client.docs["graph.json"]["nodes"]
