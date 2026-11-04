# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W846: the page harness reads the kernel's ListenOverflows count for a page failure."""

from webpage import listen_overflows

NETSTAT = """\
TcpExt: SyncookiesSent SyncookiesRecv ListenOverflows ListenDrops
TcpExt: 0 0 7 9
IpExt: InNoRoutes InTruncatedPkts
IpExt: 0 0
"""
SEVEN = 7


def test_the_overflow_count_is_the_value_under_its_column() -> None:
    """The count read is the one under ListenOverflows, not a neighbour's."""
    assert listen_overflows(NETSTAT) == SEVEN


def test_text_without_the_column_or_the_rows_answers_minus_one() -> None:
    """A host that does not say answers -1, so the report can tell unreadable from zero."""
    assert listen_overflows("TcpExt: SyncookiesSent\nTcpExt: 0\n") == -1
    assert listen_overflows("") == -1
