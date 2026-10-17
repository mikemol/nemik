# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W565: the run logs luthen publishes into the export, read as prov:Activity rows.

luthen-observability (85a0035c) publishes each migrated run log as runs/<stream>.jsonl in its
nemik export, one JSON object per line and only rows on the run-row shape, with runs/index.json
saying {stream: {rows, unmigrated}} where `unmigrated` counts the source lines that predate the
shape. This reads every stream through nemik.runrows.run_graph and carries those counts, so log
health can be reported without publishing the old rows.
"""

import json
from pathlib import Path

from rdflib import Graph

from nemik.runrows import run_graph

STREAMS = ("apply_set_runs", "apply_ledger", "reaper_runs", "tier_rehearsal")
INDEX = "index.json"


def unmigrated_at_source(directory: Path) -> dict[str, int]:
    """Read how many source lines of each stream predate the run-row shape.

    Args:
        directory: The export's runs/ directory.

    Returns:
        stream -> unmigrated lines at the source, from index.json; empty when it is missing or
        unreadable, and a stream with no usable count is left out.

    """
    try:
        doc: object = json.loads((directory / INDEX).read_text(encoding="utf-8"))
    except OSError:
        return {}
    except ValueError:
        return {}
    out: dict[str, int] = {}
    if not isinstance(doc, dict):
        return out
    for stream in STREAMS:
        entry: object = doc.get(stream)
        count: object = entry.get("unmigrated") if isinstance(entry, dict) else None
        if isinstance(count, int) and not isinstance(count, bool):
            out[stream] = count
    return out


def runs_graph(directory: Path) -> tuple[Graph, dict[str, int]]:
    """Read every published stream that is present.

    Args:
        directory: The export's runs/ directory.

    Returns:
        (the merged graph of run activities, stream -> lines in the published file that were not
        run rows). A stream whose file is missing contributes nothing and is not counted.

    """
    graph = Graph()
    broken: dict[str, int] = {}
    for stream in STREAMS:
        path = directory / f"{stream}.jsonl"
        if not path.is_file():
            continue
        part, bad = run_graph(stream, path)
        graph += part
        broken[stream] = bad
    return graph, broken
