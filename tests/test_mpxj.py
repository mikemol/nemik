# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W446: a real MSPDI reader, MPXJ, reads nemik-export and finds the links nemik wrote.

Run under the pinned Temurin JRE with MPXJ's MSPDI closure (W445). MPXJ's own query command prints a
relationship line per task, `ID<TAB>name<TAB>predecessor IDs<TAB>successor IDs`. The successor
column
repeats the task's own ID (the sample prints a successor relation's predecessor end), so only the
predecessor column is read. nemik writes each task's ID as its UID, so IDs map back to cites.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.blocks import annotate
from nemik.check import QUEUE, workstream_files
from nemik.mspdi import write
from nemik.projection import project

FLEET = Path(__file__).parent / "fixtures" / "fleet"
RELATION = re.compile(r"^(\d+)\t[^\t]*\t\"?([\d,]*)\"?\t")


def _fleet() -> Graph:
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def test_mpxj_reads_every_in_file_link(tmp_path: Path) -> None:
    java = os.environ.get("NEMIK_JAVA")
    classpath = os.environ.get("NEMIK_MPXJ_CLASSPATH")
    if not java or not classpath:
        pytest.skip("the pinned JRE and MPXJ jars come from bazel (W445)")
    tasks = project(_fleet())
    cite = {t.uid: t.cite for t in tasks}
    expected = {
        (t.cite, link.cite)
        for t in tasks
        for link in t.preds
        if link.cite in cite.values()
    }
    assert expected, "the fixture has in-file links, so the comparison is not vacuous"
    doc = tmp_path / "fleet.xml"
    doc.write_text(write(tasks))
    out = subprocess.run(
        [
            os.path.abspath(java),
            "-cp",
            ":".join(os.path.abspath(p) for p in classpath.split()),
            "org.mpxj.sample.MpxjQuery",
            str(doc),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    ).stdout
    read: set[tuple[str, str]] = set()
    for line in out.splitlines():
        m = RELATION.match(line)
        if m and m[2]:
            read.update((cite[int(m[1])], cite[int(pred)]) for pred in m[2].split(","))
    assert read == expected, (
        f"missing {sorted(expected - read)[:5]}, extra {sorted(read - expected)[:5]}"
    )
