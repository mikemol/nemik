# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W565: the live model reads luthen's published run logs into its graph."""

import json
from pathlib import Path

from rdflib import RDF
from rdflib.namespace import PROV

from nemik.serve import Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"
ROW = {
    "ts": "2026-10-16T00:09:04Z",
    "run_id": "d12246912a134f44994f0fcc89421962",
    "trigger": "systemd-unit",
    "exit": 3,
    "verdict": {"state": "deferred"},
}


def test_a_model_without_runs_has_no_activities() -> None:
    """Nothing changes unless a runs directory is given."""
    model = Model(FLEET)
    model.refresh()
    assert not list(model.graph.subjects(RDF.type, PROV.Activity))


def test_a_model_with_runs_reads_the_activities_and_follows_the_logs(
    tmp_path: Path,
) -> None:
    """One run row is one activity, and a changed log rebuilds the model."""
    log = tmp_path / "apply_set_runs.jsonl"
    log.write_text(json.dumps(ROW) + "\n", encoding="utf-8")
    model = Model(FLEET, runs=tmp_path)
    model.refresh()
    assert len(list(model.graph.subjects(RDF.type, PROV.Activity))) == 1
    later = {**ROW, "run_id": "0" * 32}
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(later) + "\n")
    model.refresh()
    runs = {ROW["run_id"], later["run_id"]}
    assert len(list(model.graph.subjects(RDF.type, PROV.Activity))) == len(runs)
