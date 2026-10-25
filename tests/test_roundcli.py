# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: the round printed for a repo takes its size from the stacks it landed."""

from pathlib import Path

from nemik.landings import Landing, document
from nemik.roundcli import round_document, round_lines, sizes_of, write_round_file

RANKED = [
    ("W5", "9.0", "first"),
    ("W2", "4.5", "second"),
    ("W9", "1.0", "third"),
    ("W1", "0.0", "fourth"),
]
STAMP = "2026-10-25T00:00:00Z"
ROWS: list[dict[str, object]] = [
    {"symbol": "W5", "salience": "9.0", "title": "first"},
    {"symbol": "W2", "salience": "4.5", "title": "second"},
    {"symbol": "W9", "salience": "1.0", "title": "third"},
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


def test_a_median_stack_below_the_floor_is_lifted_to_it(tmp_path: Path) -> None:
    """Stacks of 2, 1 and 3: the median 2 is under the floor of 3, so the top three cards."""
    lines = round_lines("alpha", RANKED, _file(tmp_path))
    assert lines[0] == "round alpha: 3 of 4 cards (size 3, from floor)"
    assert [line.split()[1] for line in lines[1:]] == ["W5", "W2", "W9"]


def test_without_a_landing_file_the_round_is_the_floor() -> None:
    """No history: the floor, from floor, as for a repo that lands outside mikemol-commit."""
    lines = round_lines("alpha", RANKED, None)
    assert lines[0] == "round alpha: 3 of 4 cards (size 3, from floor)"
    assert [line.split()[1] for line in lines[1:]] == ["W5", "W2", "W9"]


def test_the_round_file_holds_each_repos_round_sized_by_its_own_stacks(
    tmp_path: Path,
) -> None:
    """Alpha's median stack of 2 is lifted to the floor of 3; beta's one stack of 5 takes all."""
    text = round_document({"beta": ROWS, "alpha": ROWS}, _file(tmp_path), STAMP)
    assert text.splitlines() == [
        '{"as_of": "2026-10-25T00:00:00Z"}',
        '{"repo": "alpha", "symbol": "W5", "rank": "1", "salience": "9"}',
        '{"repo": "alpha", "symbol": "W2", "rank": "2", "salience": "4.5"}',
        '{"repo": "alpha", "symbol": "W9", "rank": "3", "salience": "1"}',
        '{"repo": "beta", "symbol": "W5", "rank": "1", "salience": "9"}',
        '{"repo": "beta", "symbol": "W2", "rank": "2", "salience": "4.5"}',
        '{"repo": "beta", "symbol": "W9", "rank": "3", "salience": "1"}',
    ]


def test_the_round_file_is_written_whole_to_the_path_named(tmp_path: Path) -> None:
    """The file lands at the path, with no temporary left beside it."""
    path = tmp_path / "cache" / "round.json"
    write_round_file({"alpha": ROWS}, None, path)
    assert path.read_text(encoding="utf-8").splitlines()[0].startswith('{"as_of": "')
    assert [p.name for p in path.parent.iterdir()] == ["round.json"]
