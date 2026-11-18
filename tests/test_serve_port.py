# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1060: the port a test's server listens on is the one the server bound and said so.

The old pattern picked a free port by binding port 0 and closing it, started nemik-serve on that
number and called the server up once a connection to it succeeded. Between the close and the
server's bind another process can take the port, and the connection then succeeds against that
process. These tests force that interleaving: a decoy takes the port in the gap. The decoy is a
bare listening socket (nemik:W2261: no test builds a stdlib socket server).
"""

import socket
from pathlib import Path
from typing import Protocol

import installed

FLEET = Path(__file__).parent / "fixtures" / "fleet"
LISTENING = "listening"
LINE_WORDS = 2
LOOPBACK = "127.0.0.1"


class _Named(Protocol):
    """A bound socket, as far as the port it answers is read (the stdlib types it as Any)."""

    def getsockname(self) -> tuple[str, int]:
        """Give the bound address."""
        ...


def _port(held: _Named) -> int:
    """Read the port a bound socket holds.

    Returns:
        The port.

    """
    return held.getsockname()[1]


def _hold(port: int) -> socket.socket:
    """Take a port with a bare listening socket on the loopback.

    Returns:
        The listening socket.

    """
    held = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    held.bind((LOOPBACK, port))
    held.listen()
    return held


def test_a_connect_to_a_picked_port_cannot_tell_whose_server_answered() -> None:
    """The old check passes against a decoy that took the port after the pick."""
    pick = _hold(0)
    port = _port(pick)
    pick.close()
    decoy = _hold(port)
    try:
        socket.create_connection((LOOPBACK, port), timeout=5).close()
    finally:
        decoy.close()


def test_a_server_whose_port_was_taken_does_not_say_it_listens() -> None:
    """The handshake is the server's own line, so a decoy on the port cannot make it appear."""
    decoy = _hold(0)
    try:
        port = str(_port(decoy))
        told = installed.announced("nemik-serve", "--root", str(FLEET), "--port", port)
    finally:
        decoy.close()
    assert told == []


def test_a_server_on_port_zero_says_the_port_it_bound() -> None:
    """With port 0 the line is "listening" and a port that is not 0, from the bound socket."""
    told = installed.announced("nemik-serve", "--root", str(FLEET), "--port", "0")
    assert len(told) == LINE_WORDS
    assert told[0] == LISTENING
    assert told[1].isdigit()
    assert told[1] != "0"
