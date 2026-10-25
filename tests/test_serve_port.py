# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1060: the port a test's server listens on is the one the server bound and said so.

The old pattern picked a free port by binding port 0 and closing it, started nemik-serve on that
number and called the server up once a connection to it succeeded. Between the close and the
server's bind another process can take the port, and the connection then succeeds against that
process. These tests force that interleaving: a decoy takes the port in the gap.
"""

import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import installed

FLEET = Path(__file__).parent / "fixtures" / "fleet"
LISTENING = "listening"
LINE_WORDS = 2
LOOPBACK = "127.0.0.1"


def test_a_connect_to_a_picked_port_cannot_tell_whose_server_answered() -> None:
    """The old check passes against a decoy that took the port after the pick."""
    pick = HTTPServer((LOOPBACK, 0), BaseHTTPRequestHandler)
    port = pick.server_address[1]
    pick.server_close()
    decoy = HTTPServer((LOOPBACK, port), BaseHTTPRequestHandler)
    try:
        socket.create_connection((LOOPBACK, port), timeout=5).close()
    finally:
        decoy.server_close()


def test_a_server_whose_port_was_taken_does_not_say_it_listens() -> None:
    """The handshake is the server's own line, so a decoy on the port cannot make it appear."""
    decoy = HTTPServer((LOOPBACK, 0), BaseHTTPRequestHandler)
    try:
        port = str(decoy.server_address[1])
        told = installed.announced("nemik-serve", "--root", str(FLEET), "--port", port)
    finally:
        decoy.server_close()
    assert told == []


def test_a_server_on_port_zero_says_the_port_it_bound() -> None:
    """With port 0 the line is "listening" and a port that is not 0, from the bound socket."""
    told = installed.announced("nemik-serve", "--root", str(FLEET), "--port", "0")
    assert len(told) == LINE_WORDS
    assert told[0] == LISTENING
    assert told[1].isdigit()
    assert told[1] != "0"
