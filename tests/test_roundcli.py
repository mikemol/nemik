# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: the round printed for a repo takes its size from the stacks it landed."""

from pathlib import Path

from nemik.landings import Landing, document
from nemik.roundcli import round_lines, sizes_of

RANKED = [
    ("W5", "9.0", "first"),
    ("W2", "4.5", "second"),
    ("W9", "1.0", "third"),
    ("W1", "0.0", "fourth"),
]


def _file(tmp_path: Path) -> Path:
    """Write a landing file: alpha landed stacks of 2, 1 and 3 cards, beta one of 5.

    Returns:
        The file's path.

    """
    gates = [("alpha", "100"), ("alpha", "100"), ("alpha", "200")]
    gates += [("alpha", "300")] * 3 + [("beta", "400")] * 5
    rows = [Landing(repo, "sha", "W1", int(gate), "t") for repo, gate in gates]
    path = tmp_path / "landings.json"
    path.write_text(document(rows, "2026-10-25T00:00:00Z"), encoding="utf-8")
    return path


def test_the_stack_sizes_are_the_runs_of_equal_gate_times_per_repo(
    tmp_path: Path,
) -> None:
    """Alpha's landings read as stacks of 2, 1 and 3; beta's as one of 5."""
    path = _file(tmp_path)
    assert sizes_of("alpha", path) == [2, 1, 3]
    assert sizes_of("beta", path) == [5]


def test_the_round_is_the_median_stack_size_of_the_top_of_the_ranking(
    tmp_path: Path,
) -> None:
    """Stacks of 2, 1 and 3: the median 2, so the top two cards."""
    lines = round_lines("alpha", RANKED, _file(tmp_path))
    assert lines[0] == "round alpha: 2 of 4 ready cards (size 2, from landings)"
    assert [line.split()[1] for line in lines[1:]] == ["W5", "W2"]


def test_without_a_landing_file_the_round_is_one_card() -> None:
    """No history: one card, from none."""
    lines = round_lines("alpha", RANKED, None)
    assert lines[0] == "round alpha: 1 of 4 ready cards (size 1, from none)"
    assert [line.split()[1] for line in lines[1:]] == ["W5"]
