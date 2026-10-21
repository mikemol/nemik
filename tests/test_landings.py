# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W751: commit landings read from VictoriaLogs lines into a gate-time series per repo."""

from nemik.landings import records, series

NEMIK_LATE = (
    '{"_msg":"{\\"event\\": \\"landing\\", \\"repo\\": \\"nemik\\", \\"sha\\": \\"bb9ba08\\", '
    '\\"card\\": \\"W829\\", \\"gate_s\\": \\"487\\", \\"pushed\\": \\"PUSHED\\", '
    '\\"verdict\\": \\"COMMITTED\\"}","_time":"2026-10-21T04:28:48.452386876Z"}'
)
NEMIK_EARLY = (
    '{"_msg":"{\\"event\\": \\"landing\\", \\"repo\\": \\"nemik\\", \\"sha\\": \\"d48dfe1\\", '
    '\\"card\\": \\"W827\\", \\"gate_s\\": \\"692\\", \\"pushed\\": \\"PUSHED\\", '
    '\\"verdict\\": \\"COMMITTED\\"}","_time":"2026-10-21T02:31:49.000000000Z"}'
)
MTOOLS = (
    '{"_msg":"{\\"event\\": \\"landing\\", \\"repo\\": \\"mtools\\", \\"sha\\": \\"f39dd23\\", '
    '\\"card\\": \\"W1651\\", \\"gate_s\\": \\"938\\", \\"pushed\\": \\"PUSHED\\", '
    '\\"verdict\\": \\"COMMITTED\\"}","_time":"2026-10-21T05:39:49.113780932Z"}'
)
OTHER_EVENT = (
    '{"_msg":"{\\"event\\": \\"tick\\", \\"repo\\": \\"nemik\\"}",'
    '"_time":"2026-10-21T01:00:00Z"}'
)
NEMIK_GATES = [692, 487]
MTOOLS_GATES = [938]
THREE = 3


def test_landings_come_out_oldest_first_whatever_order_the_answer_had() -> None:
    """VictoriaLogs answers newest first; the series wants the order they landed."""
    rows = records([MTOOLS, NEMIK_LATE, NEMIK_EARLY])
    assert [row.sha for row in rows] == ["d48dfe1", "bb9ba08", "f39dd23"]
    assert len(rows) == THREE
    assert rows[0].card == "W827"


def test_a_line_that_is_not_a_landing_record_is_skipped() -> None:
    """Junk, an empty line and another event do not hide the real landings."""
    rows = records(["not json", "", OTHER_EVENT, NEMIK_LATE])
    assert [row.sha for row in rows] == ["bb9ba08"]


def test_each_repo_gets_its_gate_seconds_in_landing_order() -> None:
    """The series is per repo, in the order the commits landed."""
    got = series(records([MTOOLS, NEMIK_LATE, NEMIK_EARLY]))
    assert got == {"nemik": NEMIK_GATES, "mtools": MTOOLS_GATES}
