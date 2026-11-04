# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W846: the page servers listen with a backlog above a browser's parallel connects.

socketserver's default listen backlog is 5. A browser opens six script requests at once, and the
commit gate runs hundreds of processes beside the server, so a descheduled accept thread lets the
accept queue overflow and a request for a file the server can serve fails with the server alive:
the signature of the popLater flake (five scripts failed at once, nemik-serve alive, stderr empty).
Both modules' PageServer sets request_queue_size to their BACKLOG constant, which is what is pinned
here (the class itself is typed with Any by the standard library's stubs). The property is pinned,
not the interleaving, which is not forced here.
"""

from nemik import serve, staticserve

BROWSER_PARALLEL = 6


def test_the_live_server_backlog_exceeds_a_browsers_parallel_connects() -> None:
    """The live server's accept queue holds more than the six requests a page makes at once."""
    assert serve.BACKLOG > BROWSER_PARALLEL


def test_the_static_server_backlog_exceeds_a_browsers_parallel_connects() -> None:
    """The static server's accept queue holds more than the six requests a page makes at once."""
    assert staticserve.BACKLOG > BROWSER_PARALLEL
