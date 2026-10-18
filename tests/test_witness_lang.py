# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W539: a waypoint's declared witness language is read; the sniff is only a fallback."""

import json
from pathlib import Path

from nemik.witnesses import is_rego, open_witnesses

PLAIN = "up == 0"
READS_INPUT = 'input.file["/x"].exists'


def test_a_declared_language_overrides_the_sniff_both_ways() -> None:
    """Rego declared on PromQL-looking text, and PromQL declared on text that names input."""
    assert is_rego(PLAIN, "rego")
    assert not is_rego(READS_INPUT, "promql")


def test_no_declared_language_still_sniffs() -> None:
    """The fallback is unchanged for a witness that has no witness_lang."""
    assert is_rego(READS_INPUT)
    assert not is_rego(PLAIN)
    assert is_rego(READS_INPUT, "")


def test_the_queue_scan_carries_the_language(tmp_path: Path) -> None:
    """open_witnesses returns the card's witness_lang, or an empty string when it has none."""
    queue = tmp_path / "alpha" / "paths-forward.json"
    queue.parent.mkdir()
    first: dict[str, str] = {
        "symbol": "W1",
        "status": "blocked",
        "witness": PLAIN,
        "witness_lang": "promql",
    }
    second: dict[str, str] = {
        "symbol": "W2",
        "status": "blocked",
        "witness": READS_INPUT,
    }
    doc: dict[str, list[dict[str, str]]] = {"waypoints": [first, second]}
    queue.write_text(json.dumps(doc))
    found = open_witnesses(tmp_path)
    assert [(sym, lang) for _, _, sym, _, lang in found] == [
        ("W1", "promql"),
        ("W2", ""),
    ]
