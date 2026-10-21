# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""landings: the fleet's commit landings as a gate-time series per repo (nemik:W751, W743).

After a stack's verdict mikemol-commit sends one log record per committed line (mtools:W1738,
service mikemol-commit): its _msg is {"event", "repo", "sha", "card", "gate_s", "pushed",
"verdict"} as JSON text and its _time stamps the landing. Fetching the lines is
endpoint.vlogs_lines; this module is the pure part, reading them into rows and giving each repo's
gate times in the order they landed. The lines are read with hostroot's flat-JSON reader.
"""

from .hostroot import fields

EVENT = "landing"


class Landing:
    """One commit landing as the stream reported it."""

    def __init__(self, repo: str, sha: str, card: str, gate_s: int, when: str) -> None:
        """Hold the repo, the commit, its card ("-" for none), the gate seconds and the stamp."""
        self.repo = repo
        self.sha = sha
        self.card = card
        self.gate_s = gate_s
        self.when = when


def _first(body: dict[str, list[str]], key: str) -> str:
    """Read the single string a key holds.

    Returns:
        The key's first item.

    Raises:
        ValueError: When the key is absent or holds no item.

    """
    items = body.get(key, [])
    if len(items) == 0:
        message = f"no {key}"
        raise ValueError(message)
    return items[0]


def _landing(line: str) -> list[Landing]:
    """Read one record of a VictoriaLogs answer.

    Returns:
        The landing, or nothing when the line is not a landing record.

    """
    try:
        record = fields(line)
        body = fields(_first(record, "_msg"))
        if _first(body, "event") != EVENT:
            return []
        return [
            Landing(
                _first(body, "repo"),
                _first(body, "sha"),
                _first(body, "card"),
                int(_first(body, "gate_s")),
                _first(record, "_time"),
            )
        ]
    except ValueError:
        return []


def _stamp(row: Landing) -> str:
    """Give the sort key of a landing.

    Returns:
        Its stamp, which as an RFC 3339 UTC string sorts as time does.

    """
    return row.when


def records(lines: list[str]) -> list[Landing]:
    """Read the lines of a VictoriaLogs answer into landings, oldest first.

    A line that is not a landing record is skipped, so one bad line does not hide the series.

    Args:
        lines: The answer's lines, in the order read (newest first from VictoriaLogs).

    Returns:
        The landings sorted by their stamp.

    """
    rows: list[Landing] = []
    for line in lines:
        rows.extend(_landing(line))
    return sorted(rows, key=_stamp)


AS_OF_KEY = '"as_of": "'


def _quoted(text: str) -> str:
    """Quote a string for JSON (a repo, sha or card holds nothing needing more than these).

    Returns:
        The JSON string literal for `text`.

    """
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def row_json(row: Landing) -> str:
    """Write one landing as a JSON object.

    Returns:
        The object, keys in a fixed order, the gate seconds a string as the stream has them.

    """
    return (
        f'{{"repo": {_quoted(row.repo)}, "sha": {_quoted(row.sha)}, '
        f'"card": {_quoted(row.card)}, "gate_s": "{row.gate_s}", "when": {_quoted(row.when)}}}'
    )


def document(rows: list[Landing], as_of: str) -> str:
    """Write the document the host leaves for nemik-serve: the stamp, then a row per line.

    Args:
        rows: The landings, oldest first.
        as_of: When the stream was read, an ISO stamp.

    Returns:
        The file's text.

    """
    body = ",\n  ".join(row_json(row) for row in rows)
    return f'{{"as_of": {_quoted(as_of)}, "rows": [\n  {body}\n]}}\n'


def read_document(text: str) -> tuple[str, list[Landing]]:
    """Read the document document() writes.

    Args:
        text: The file's text.

    Returns:
        When the stream was read, and the landings in the order written.

    Raises:
        ValueError: When the first line carries no as_of or a row line cannot be read.

    """
    lines = text.splitlines()
    head = lines[0] if lines else ""
    at = head.find(AS_OF_KEY)
    if at < 0:
        message = "no as_of on the first line"
        raise ValueError(message)
    start = at + len(AS_OF_KEY)
    as_of = head[start : head.find('"', start)]
    rows: list[Landing] = []
    for line in lines[1:]:
        body = line.strip().rstrip(",")
        if body.startswith("{"):
            fields_of = fields(body)
            rows.append(
                Landing(
                    _first(fields_of, "repo"),
                    _first(fields_of, "sha"),
                    _first(fields_of, "card"),
                    int(_first(fields_of, "gate_s")),
                    _first(fields_of, "when"),
                )
            )
    return as_of, rows


def series(rows: list[Landing]) -> dict[str, list[int]]:
    """Give each repo's gate seconds in the order its commits landed.

    Args:
        rows: Landings, oldest first, as records() returns them.

    Returns:
        {repo: [gate_s, ...]}.

    """
    out: dict[str, list[int]] = {}
    for row in rows:
        if row.repo not in out:
            out[row.repo] = []
        out[row.repo].append(row.gate_s)
    return out
