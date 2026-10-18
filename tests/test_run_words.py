# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W555: lifecycle words in a run row's detail are flagged, as in a card's next step."""

import json
from pathlib import Path

from nemik.adapter import stray_words
from nemik.check import shapes
from nemik.runlogs import runs_graph
from nemik.shaclinc import findings

ROW: dict[str, object] = {
    "ts": "2026-10-16T00:09:04Z",
    "run_id": "d12246912a134f44994f0fcc89421962",
    "trigger": "systemd-unit",
    "exit": 0,
}
DONE: dict[str, str] = {"state": "done"}


def _row(detail: str) -> str:
    """Write one run row with a detail, as a log line.

    Args:
        detail: The row's detail text.

    Returns:
        The line.

    """
    body: dict[str, object] = {**ROW, "detail": detail, "verdict": DONE}
    return json.dumps(body) + "\n"


def test_the_words_are_found_once_and_lower_cased() -> None:
    """Deployed and SHIPPED are strays, a live session is not, and repeats count once."""
    found = stray_words("Deployed, then SHIPPED; deployed again to a live session")
    assert found == ["deployed", "shipped"]


def test_a_run_detail_with_a_stray_word_is_flagged_as_info(tmp_path: Path) -> None:
    """The activity carries the word and the shape on prov:Activity reports it."""
    (tmp_path / "apply_set_runs.jsonl").write_text(
        _row("shipped to the host"), encoding="utf-8"
    )
    graph, _ = runs_graph(tmp_path)
    found = findings("run-words", graph, shapes())
    rows = [(sev.rsplit("#", 1)[-1], "shipped" in msg) for _, sev, msg in found]
    assert rows == [("Info", True)]


def test_a_clean_detail_or_none_is_not_flagged(tmp_path: Path) -> None:
    """Landed is a lifecycle step, not a stray; a row with no detail has nothing to flag."""
    no_detail: dict[str, object] = {**ROW, "verdict": DONE}
    lines = _row("landed on the host") + json.dumps(no_detail) + "\n"
    (tmp_path / "apply_set_runs.jsonl").write_text(lines, encoding="utf-8")
    graph, _ = runs_graph(tmp_path)
    assert findings("run-words-clean", graph, shapes()) == []
