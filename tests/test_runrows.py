# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W558: run rows become activities, and the reader's verdicts are jsonschema's."""

import json
from pathlib import Path

import jsonschema
import pytest
from rdflib import RDF
from rdflib.namespace import PROV

from nemik.runrows import SCHEMA, run_graph, valid

GOOD = {
    "ts": "2026-10-16T00:09:04Z",
    "run_id": "d12246912a134f44994f0fcc89421962",
    "trigger": "systemd-unit",
    "exit": 3,
    "verdict": {"state": "deferred"},
    "detail": "a pre-flight gate is not met",
    "inputs_digest": "a" * 64,
}
SHAPES = {
    "clean": GOOD,
    "apply-set-as-audited": {"set": "main", "exit": 0, "verdict": "{}", "when": "x"},
    "reaper-as-audited": {"event": "verdict", "exit": 0, "verdict": {"state": "done"}},
    "apply-ledger-as-audited": {"apply_exit": 0, "when": "2026-10-15T20:53:12Z"},
    "string-verdict": {**GOOD, "verdict": '{"state": "applied"}'},
    "verdict-without-state": {**GOOD, "verdict": {"why": "x"}},
    "exit-is-a-bool": {**GOOD, "exit": True},
    "empty-run-id": {**GOOD, "run_id": ""},
    "short-digest": {**GOOD, "inputs_digest": "abc"},
}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_the_reader_agrees_with_jsonschema(name: str) -> None:
    """Every shape W534 audited, plus the edges of the schema, gets jsonschema's verdict."""
    row = SHAPES[name]
    assert valid(row) is jsonschema.Draft202012Validator(SCHEMA).is_valid(row), name


def test_a_timestamp_without_an_offset_is_refused() -> None:
    """The jsonschema package skips date-time without an extra one, so this reader checks it."""
    assert not valid({**GOOD, "ts": "2026-10-16T00:09:04"})


def test_a_log_becomes_activities_and_counts_the_rest(tmp_path: Path) -> None:
    """Valid rows are activities with their fields, and old or broken lines are counted."""
    log = tmp_path / "apply-set-runs.jsonl"
    old = {"set": "main", "exit": 0, "verdict": "{}", "when": "x"}
    lines = [json.dumps(GOOD), json.dumps(old), "not json", json.dumps(old)]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    graph, unmigrated = run_graph("apply-set-runs", log)
    assert unmigrated == len(lines) - 1
    activities = list(graph.subjects(RDF.type, PROV.Activity))
    assert len(activities) == 1
    node = activities[0]
    assert str(node).endswith(f"/{GOOD['run_id']}/{GOOD['ts']}")
    values = {
        str(p).rsplit("#", 1)[-1]: str(o) for p, o in graph.predicate_objects(node)
    }
    assert values["trigger"] == "systemd-unit"
    assert values["exitCode"] == "3"
    assert values["verdictState"] == "deferred"
    assert values["stream"] == "apply-set-runs"
