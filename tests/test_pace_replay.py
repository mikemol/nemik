# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pace_replay judges a ratchet's window under the current and the proposed rule (nemik:W2020)."""

from pace_replay import (
    MYPY,
    RUFF,
    counts,
    entries,
    fall,
    measured,
    pairs,
    replay,
    score,
    split_log,
    stalled,
    verdict,
)

WINDOW = 10
WINDOW_PLUS_ONE = 11
FALL_OF_FOUR = 4
THREE_ENTRIES = 3
PAIRS_IN_LINT = 3
COUNT_IN_LINT = 6
EPOCH = 1_700_000_000
BASELINE_TEXT = '{"a": {"as_written": "x", "stripped": "y"}, "b": {"as_written": "z"}}'
LINT_TEXT = '{"a.py": {"PLC0415": 3, "S404": 1}, "b.py": {"misc": 2}, "c.py": 5}'
SRC = ["src/nemik/a.py"]
LOG_TEXT = (
    f"@aaa {EPOCH}\nsrc/nemik/a.py\ndocs/b.md\n\n@bbb\n\n@ccc {EPOCH + 1}\nx.py\n"
)


def test_pairs_count_rules_and_counts_sum_them() -> None:
    """A pair is a (file, rule) entry, a count its integer; anything else reads as zero."""
    assert pairs(LINT_TEXT) == PAIRS_IN_LINT
    assert counts(LINT_TEXT) == COUNT_IN_LINT
    assert pairs("not json") == 0
    assert counts("[]") == 0


def test_measured_follows_the_spec_of_the_ratchet() -> None:
    """Each ratchet measures its own baseline and the python under its own prefixes."""
    assert measured(["tests/test_x.py"], RUFF)
    assert measured(["tools/y.py"], MYPY)
    assert measured(["ruff-baseline.json"], RUFF)
    assert not measured(["mypy-baseline.json"], RUFF)
    assert not measured(["docs/x.md"], RUFF)
    assert not measured(["tests/test_x.py"])


def test_entries_counts_each_mode_of_each_module() -> None:
    """The codon baseline has one entry per module and compile mode."""
    assert entries(BASELINE_TEXT) == THREE_ENTRIES
    assert entries("not json") == 0
    assert entries("[]") == 0


def test_measured_is_src_python_or_the_baseline() -> None:
    """The codon ratchet measures python under src/nemik and its baseline, nothing else."""
    assert measured(["src/nemik/rank.py"])
    assert measured(["codon-baseline.json"])
    assert not measured(["docs/x.md", "tools/y.py", "src/nemik/data/z.json"])


def test_fall_needs_a_full_window_of_history() -> None:
    """With too few values there is no fall to report."""
    assert fall([5] * WINDOW_PLUS_ONE) == 0
    assert fall([9, *([5] * WINDOW)]) == FALL_OF_FOUR
    assert fall([5, 5]) == 0


def test_verdict_is_ok_only_when_the_window_fell_enough() -> None:
    """A fall of four is ok and a fall of one is behind."""
    assert verdict([9, *([5] * WINDOW)]) == "ok"
    assert verdict([6, *([5] * WINDOW)]) == "behind"


def test_queue_only_landings_age_only_the_current_window() -> None:
    """Quiet landings push a fall out of the current window and leave the proposed one."""
    falling = [(f"s{i}", SRC, 30 - 2 * i) for i in range(WINDOW_PLUS_ONE)]
    quiet = [(f"q{i}", ["queue.json"], 10) for i in range(WINDOW_PLUS_ONE)]
    differing = replay(falling + quiet)
    assert differing
    for _, current, proposed in differing:
        assert current == "behind"
        assert proposed == "ok"


def test_split_log_pairs_each_commit_with_its_time_and_files() -> None:
    """One triple per commit: its sha, its epoch (0 when absent) and its files."""
    assert split_log(LOG_TEXT) == [
        ("aaa", EPOCH, ["src/nemik/a.py", "docs/b.md"]),
        ("bbb", 0, []),
        ("ccc", EPOCH + 1, ["x.py"]),
    ]


def test_stalled_needs_ten_measured_landings_after() -> None:
    """A landing with fewer than ten measured landings after it is not judged."""
    flat = [(f"s{i}", SRC, 10) for i in range(WINDOW_PLUS_ONE + 1)]
    assert stalled(flat, 0) is True
    assert stalled(flat, 2) is None
    fell = [(f"s{i}", SRC, 10 if i == 0 else 9) for i in range(WINDOW_PLUS_ONE)]
    assert stalled(fell, 0) is False


def test_a_verdict_ok_on_a_stalled_landing_is_a_false_ok() -> None:
    """MUTANT: a rule that says ok while the value then stays flat is scored as a false ok."""
    falling = [(f"s{i}", SRC, 30 - 2 * i) for i in range(WINDOW_PLUS_ONE)]
    flat = [(f"t{i}", SRC, 10) for i in range(WINDOW_PLUS_ONE)]
    result = score(falling + flat)
    assert "s10" in result["current false ok"]
    assert "s10" in result["proposed false ok"]
    assert "s10" in result["scored"]
