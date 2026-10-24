# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""logactivities: a repo's wait records read back as ActivityStreams activities (nemik:W947, W945).

waitlog sends one log record per pair of repos whose _msg is an ActivityStreams Update as JSON text
(nemik:W944, docs/federation-log.md) and whose _time stamps it. Fetching the lines is
endpoint.vlogs_lines; this module is the pure part: it reads the lines of a VictoriaLogs answer and
gives the activities one actor published, oldest first, each with the record's time as `published`.
A line that is not such an activity (another service's record, a body that does not parse) is left
out rather than guessed at. The lines are read with hostroot's flat-JSON reader.
"""

from nemik.hostroot import fields

WAIT_ID = "urn:nemik:wait:"
KEYS = ("id", "type", "actor", "object", "target", "content")


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


def _activity(line: str) -> list[dict[str, str]]:
    """Read one record of a VictoriaLogs answer.

    Returns:
        The activity with `published` added from the record's time, or nothing when the line is not
        a wait activity.

    """
    try:
        record = fields(line)
        body = fields(_first(record, "_msg"))
        out = {key: _first(body, key) for key in KEYS}
        out["published"] = _first(record, "_time")
    except ValueError:
        return []
    if not out["id"].startswith(WAIT_ID):
        return []
    return [out]


def _order(activity: dict[str, str]) -> tuple[str, str]:
    """Order activities by when they were published, then by id.

    Returns:
        The sort key.

    """
    return activity["published"], activity["id"]


def activities(lines: list[str], repo: str) -> list[dict[str, str]]:
    """Give the wait activities a repo published, oldest first.

    Args:
        lines: The JSON records of a VictoriaLogs answer, one per line.
        repo: The repo whose activities are wanted; its actor is `urn:nemik:<repo>`.

    Returns:
        Each activity as its fields (id, type, actor, object, target, content, published), ordered
        by published and then id, so the same lines give the same bytes.

    """
    actor = f"urn:nemik:{repo}"
    found = [a for line in lines for a in _activity(line) if a["actor"] == actor]
    return sorted(found, key=_order)
