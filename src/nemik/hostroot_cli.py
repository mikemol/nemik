# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-hostroot: write luthen's host-root frontier as one JSON document (nemik:W779, W461).

The stream (VictoriaLogs, stream host_root_frontier, luthen-observability:W1468) is reachable only
from the host: nemik's pod has no luthen checkout. This runs on the host, reads the newest row of
each resource, and writes {as_of, rows} to a file that nemik-serve reads with a freshness check
(nemik:W780), as it reads luthen-series.json.

With --landings it writes the commit landings instead (nemik:W751): mikemol-commit's records
(service mikemol-commit) as nemik.landings reads them, to landings.json beside the other file.

With --log-activities it writes the wait activities nemik's own log records carry (nemik:W948,
docs/federation-log.md): service nemik-waits, read by nemik.logactivities, to log-activities.json
as one flat JSON object per line (a header, then an activity per line) for the outbox. The
server never spawns, so the log is read here, on the host.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from nemik.endpoint import vlogs_lines
from nemik.hostroot import HostRow, latest, records
from nemik.landings import document as landings_document
from nemik.landings import records as landings_records
from nemik.logactivities import activities, repos

QUERY = "stream:host_root_frontier"
LANDINGS_QUERY = "service.name:mikemol-commit"
LOG_QUERY = "service.name:nemik-waits"
# one record per landing, so a few thousand reach back days; the series wants the recent ones
LANDINGS_LIMIT = 2000
LOG_LIMIT = 2000
CACHE = Path.home() / ".cache" / "nemik"
DEFAULT_OUT = CACHE / "host-root.json"
LANDINGS_OUT = CACHE / "landings.json"
LOG_OUT = CACHE / "log-activities.json"


def _quoted(text: str) -> str:
    """Quote a string for JSON.

    Returns:
        The JSON string literal for `text`.

    """
    return json.dumps(text)


class _Options(argparse.Namespace):
    """The command line, typed."""

    root: Path
    out: Path | None
    landings: bool
    log_activities: bool


def row_json(row: HostRow) -> str:
    """Write one row as a JSON object.

    Returns:
        The object, keys in a fixed order.

    """
    waits = ", ".join(_quoted(item) for item in row.waits_for)
    return (
        f'{{"id": {_quoted(row.ident)}, "state": {_quoted(row.state)}, '
        f'"waitsFor": [{waits}], "gate": {_quoted(row.gate)}, '
        f'"reading": {_quoted(row.reading)}, "as_of": {_quoted(row.as_of)}}}'
    )


def document(rows: list[HostRow], as_of: str) -> str:
    """Write the document nemik-serve reads.

    Args:
        rows: The newest row of each resource.
        as_of: When this document was read, an ISO stamp.

    Returns:
        {"as_of": ..., "rows": [...]} as JSON text.

    """
    body = ",\n  ".join(row_json(row) for row in rows)
    return f'{{"as_of": {_quoted(as_of)}, "rows": [\n  {body}\n]}}\n'


def activity_json(activity: dict[str, str]) -> str:
    """Write one activity as a JSON object.

    Returns:
        The object, its fields in the order they were read.

    """
    pairs = ", ".join(f"{_quoted(k)}: {_quoted(v)}" for k, v in activity.items())
    return "{" + pairs + "}"


def log_document(lines: list[str], as_of: str) -> str:
    """Write the document of log activities nemik-serve reads (nemik:W948).

    Args:
        lines: The JSON records of a VictoriaLogs answer.
        as_of: When the lines were read, an ISO stamp.

    Returns:
        One flat JSON object per line (nemik:W950): the first is {"as_of": ...}, then one
        line per activity, the repos sorted and each repo's activities oldest first, so the
        same lines give the same bytes. Flat lines are what logactivities.read_log reads.

    """
    header = f'{{"as_of": {_quoted(as_of)}}}'
    rows = [activity_json(a) for repo in repos(lines) for a in activities(lines, repo)]
    return "\n".join([header, *rows]) + "\n"


def _write(path: Path, text: str) -> None:
    """Write a file whole or not at all, so the server never reads half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def landings(options: _Options, stamp: str) -> int:
    """Read mikemol-commit's landing records and write the landings document.

    Returns:
        0 when written; 1 when luthen's tool could not answer or the answer held no landing.

    """
    try:
        rows = landings_records(
            vlogs_lines(LANDINGS_QUERY, options.root, LANDINGS_LIMIT)
        )
    except OSError as error:
        sys.stderr.write(f"nemik-hostroot: {error}\n")
        return 1
    if not rows:
        sys.stderr.write("nemik-hostroot: the stream answered with no landing record\n")
        return 1
    _write(options.out or LANDINGS_OUT, landings_document(rows, stamp))
    return 0


def log_activities(options: _Options, stamp: str) -> int:
    """Read nemik's own wait records and write the log activities document.

    Returns:
        0 when written; 1 when luthen's tool could not answer or the answer held no wait activity.

    """
    try:
        lines = vlogs_lines(LOG_QUERY, options.root, LOG_LIMIT)
    except OSError as error:
        sys.stderr.write(f"nemik-hostroot: {error}\n")
        return 1
    if not repos(lines):
        sys.stderr.write("nemik-hostroot: the stream answered with no wait activity\n")
        return 1
    _write(options.out or LOG_OUT, log_document(lines, stamp))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Read the stream and write the document.

    Returns:
        0 when written; 1 when luthen's tool could not answer or the answer held no row.

    """
    parser = argparse.ArgumentParser(prog="nemik-hostroot", description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "github")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--landings",
        action="store_true",
        help="write mikemol-commit's landing records (landings.json) instead of the frontier",
    )
    parser.add_argument(
        "--log-activities",
        action="store_true",
        help="write nemik's wait activities from the log (log-activities.json) instead",
    )
    options = parser.parse_args(argv, namespace=_Options())
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if options.landings:
        return landings(options, stamp)
    if options.log_activities:
        return log_activities(options, stamp)
    try:
        rows = latest(records(vlogs_lines(QUERY, options.root)))
    except OSError as error:
        sys.stderr.write(f"nemik-hostroot: {error}\n")
        return 1
    if not rows:
        sys.stderr.write("nemik-hostroot: the stream answered with no readable row\n")
        return 1
    _write(options.out or DEFAULT_OUT, document(rows, stamp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
