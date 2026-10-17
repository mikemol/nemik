# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W565: the run logs luthen publishes become activities, and the source counts ride along."""

import json
from pathlib import Path

from rdflib import RDF
from rdflib.namespace import PROV

from nemik.runlogs import runs_graph, unmigrated_at_source

ROW = {
    "ts": "2026-10-16T00:09:04Z",
    "run_id": "d12246912a134f44994f0fcc89421962",
    "trigger": "systemd-unit",
    "exit": 3,
    "verdict": {"state": "deferred"},
}


def test_a_published_stream_becomes_activities(tmp_path: Path) -> None:
    """One run row in apply_set_runs.jsonl is one activity; a stray line is counted."""
    text = json.dumps(ROW) + "\nnot json\n"
    (tmp_path / "apply_set_runs.jsonl").write_text(text, encoding="utf-8")
    graph, broken = runs_graph(tmp_path)
    assert len(list(graph.subjects(RDF.type, PROV.Activity))) == 1
    assert broken == {"apply_set_runs": 1}


def test_a_missing_stream_contributes_nothing(tmp_path: Path) -> None:
    """No files, no activities, no counts."""
    graph, broken = runs_graph(tmp_path)
    assert len(graph) == 0
    assert broken == {}


def test_the_source_counts_come_from_the_index(tmp_path: Path) -> None:
    """index.json's unmigrated counts are read; a stream without a count is left out."""
    index = {
        "apply_set_runs": {"rows": 1028, "unmigrated": 491},
        "apply_ledger": {"rows": 3},
        "reaper_runs": {"rows": 0, "unmigrated": True},
    }
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    assert unmigrated_at_source(tmp_path) == {"apply_set_runs": 491}


def test_an_unreadable_index_gives_no_counts(tmp_path: Path) -> None:
    """Missing and not-JSON both give an empty answer, not an error."""
    assert unmigrated_at_source(tmp_path) == {}
    (tmp_path / "index.json").write_text("{", encoding="utf-8")
    assert unmigrated_at_source(tmp_path) == {}
