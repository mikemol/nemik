# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1530: metrics.spool_lines counts the hook's events and skips lines that are not events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nemik.metrics import spool_lines

if TYPE_CHECKING:
    from pathlib import Path

SPOOL = """\
{"event": "UserPromptSubmit", "repo": "nemik", "source": "cron"}
[1, 2]
"text"
not json
{"event": "Stop", "repo": "nemik"}
"""


def test_a_json_line_that_is_not_an_object_is_skipped_not_fatal(tmp_path: Path) -> None:
    """A list, a string and bad JSON are skipped; the prompt and turn around them count."""
    spool = tmp_path / "events.jsonl"
    spool.write_text(SPOOL, encoding="utf-8")
    lines = spool_lines(spool)
    assert any(
        line.startswith("nemik_prompts_total{") and line.endswith(" 1")
        for line in lines
    )
    assert any(
        line.startswith("nemik_turns_total{") and line.endswith(" 1") for line in lines
    )
