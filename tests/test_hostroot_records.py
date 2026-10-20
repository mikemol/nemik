# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W774: a VictoriaLogs record of the host-root stream reads into a row."""

import json

from nemik.hostroot import fields, latest, records

ID = 'local_file.host["aer-counters-timer"]'
MESSAGE = (
    '{"as_of": "2026-10-20T14:00:49Z", "gate": "observable", '
    '"id": "local_file.host[\\"aer-counters-timer\\"]", '
    '"reading": "this process cannot read the target", "state": "blocked", '
    '"waitsFor": ["a", "b[\\"c\\"]"]}'
)


def _record(message: str) -> str:
    """Wrap a document in a record the way VictoriaLogs prints it.

    Returns:
        One line of JSON with the document, as a string, in _msg.

    """
    return '{"_msg": ' + json.dumps(message) + ', "stream": "host_root_frontier"}'


def test_a_record_reads_into_a_row_with_its_escaped_id() -> None:
    """The id keeps its quotes; waitsFor, gate and reading come across."""
    rows = records([_record(MESSAGE)])
    assert [row.ident for row in rows] == [ID]
    assert rows[0].state == "blocked"
    assert rows[0].gate == "observable"
    assert rows[0].waits_for == ["a", 'b["c"]']
    assert rows[0].as_of == "2026-10-20T14:00:49Z"


def test_a_line_that_is_not_a_record_is_skipped() -> None:
    """Garbage, a record with no _msg and a _msg with a missing field cost one line only."""
    lines = ["not json", '{"other": 1}', _record('{"id": "x"}'), _record(MESSAGE)]
    assert [row.ident for row in latest(records(lines))] == [ID]


def test_the_reader_takes_escapes_empty_lists_and_bare_values() -> None:
    """A unicode escape, an empty list, a number and a boolean each read as items."""
    body = fields('{"a": "\\u00e9\\n", "b": [], "c": 7, "d": [true, "x"]}')
    assert body == {"a": ["é\n"], "b": [], "c": ["7"], "d": ["true", "x"]}
