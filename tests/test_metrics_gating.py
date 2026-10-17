# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W355: the git-history families are computed only when asked for by name."""

from pathlib import Path

import pytest

from nemik.metrics import main

FLEET = Path(__file__).parent / "fixtures" / "fleet"
HISTORY = (
    "nemik_cards_completed_24h",
    "nemik_commits_24h",
    "nemik_cards_reopened_24h",
)


def test_a_default_run_leaves_the_history_families_out(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A plain run does no per-repo git walk, so it stays inside the relay's bound."""
    main(["--root", str(FLEET), "--spool", str(tmp_path / "none.jsonl")])
    out = capsys.readouterr().out
    assert not [name for name in HISTORY if name in out]


def test_naming_a_family_computes_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Asked for by name, the family prints its TYPE line."""
    main(
        [
            "--root",
            str(FLEET),
            "--spool",
            str(tmp_path / "none.jsonl"),
            "--family",
            "nemik_commits_24h",
        ]
    )
    assert "# TYPE nemik_commits_24h gauge" in capsys.readouterr().out
