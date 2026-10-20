# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-hostroot: write luthen's host-root frontier as one JSON document (nemik:W779, W461).

The stream (VictoriaLogs, stream host_root_frontier, luthen-observability:W1468) is reachable only
from the host: nemik's pod has no luthen checkout. This runs on the host, reads the newest row of
each resource, and writes {as_of, rows} to a file that nemik-serve reads with a freshness check
(nemik:W780), as it reads luthen-series.json.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from nemik.endpoint import vlogs_lines
from nemik.hostroot import HostRow, latest, records

QUERY = "stream:host_root_frontier"
DEFAULT_OUT = Path.home() / ".cache" / "nemik" / "host-root.json"


def _quoted(text: str) -> str:
    """Quote a string for JSON.

    Returns:
        The JSON string literal for `text`.

    """
    return json.dumps(text)


class _Options(argparse.Namespace):
    """The command line, typed."""

    root: Path
    out: Path


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


def main(argv: list[str] | None = None) -> int:
    """Read the stream and write the document.

    Returns:
        0 when written; 1 when luthen's tool could not answer or the answer held no row.

    """
    parser = argparse.ArgumentParser(prog="nemik-hostroot", description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "github")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    options = parser.parse_args(argv, namespace=_Options())
    try:
        rows = latest(records(vlogs_lines(QUERY, options.root)))
    except OSError as error:
        sys.stderr.write(f"nemik-hostroot: {error}\n")
        return 1
    if not rows:
        sys.stderr.write("nemik-hostroot: the stream answered with no readable row\n")
        return 1
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    options.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = options.out.with_suffix(".tmp")
    temporary.write_text(document(rows, stamp), encoding="utf-8")
    temporary.replace(options.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
