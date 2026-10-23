# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W783: the serving process never forks or execs, for any route it answers.

Operator goal 2026-10-20 (nemik:W781): read-only parity between the CLI tools and the web UI
"without spawning processes through UI". Here every call that starts a process raises inside the
server, and every route the handler answers is fetched: a route that spawned would answer 500
with the refusal, and this test would name it. The unit's SystemCallFilter (nemik:W788) is the
runtime rail; this is the pin.
"""

import http.client
import importlib
import os
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from nemik.serve import Model, handler

FLEET = Path(__file__).parent / "fixtures" / "fleet"
SERVER_ERROR = 500
ROUTES = [
    "/",
    "/wake",
    "/wake.json",
    "/operator",
    "/operator.json",
    "/inbound",
    "/inbound/nemik.json",
    "/goals/nemik.json",
    "/metrics",
    "/series.json",
    "/hostroot.json",
    "/landings.json",
    "/critical.json",
    "/starved.json",
    "/overlaps.json",
    "/pacing.json",
    "/oldest.json",
    "/floor-asks.json",
    "/check.json",
    "/check/ready-neither.json",
    "/check/unmanifested.json",
    "/check/integrity.json",
    "/check/letters.json",
    "/check/fold.json",
    "/graph.json",
    "/graph.ttl",
    "/vendor/cytoscape.min.js",
]
SPAWNERS = [
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
    ("os", "fork"),
    ("os", "forkpty"),
    ("os", "system"),
    ("os", "posix_spawn"),
    ("os", "posix_spawnp"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "execvp"),
    ("os", "execvpe"),
    ("os", "execl"),
    ("os", "execle"),
    ("os", "execlp"),
    ("os", "execlpe"),
    ("os", "popen"),
]


class SpawnedError(AssertionError):
    """A call that starts a process was made while serving."""


def _refuse(name: str) -> object:
    """Build a stand-in for a spawning call that raises when it is called.

    Returns:
        The stand-in.

    """

    def refused(*args: object, **kwargs: object) -> None:
        del args, kwargs
        message = f"{name} was called while serving"
        raise SpawnedError(message)

    return refused


@pytest.fixture(scope="module")
def server() -> Iterator[int]:
    """Serve the fixture fleet with every spawner refused.

    Yields:
        The port.

    """
    patch = pytest.MonkeyPatch()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Model(FLEET)))
    for module_name, name in SPAWNERS:
        module = importlib.import_module(module_name)
        if hasattr(module, name):
            patch.setattr(module, name, _refuse(f"{module_name}.{name}"))
    assert hasattr(os, "fork")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield int(httpd.server_address[1])
    httpd.shutdown()
    patch.undo()


@pytest.mark.parametrize("route", ROUTES)
def test_a_route_answers_without_starting_a_process(server: int, route: str) -> None:
    """GET the route: any answer but a server error means no spawner was reached."""
    connection = http.client.HTTPConnection("127.0.0.1", server, timeout=120)
    connection.request("GET", route)
    reply = connection.getresponse()
    reply.read()
    connection.close()
    assert reply.status < SERVER_ERROR, f"{route} answered {reply.status}"
