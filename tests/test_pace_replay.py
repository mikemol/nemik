# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pace_replay judges a ratchet's window under the current and the proposed rule (nemik:W2020)."""

from pace_replay import (
    CODON,
    GRID,
    MYPY,
    RUFF,
    counts,
    entries,
    fall,
    fit,
    fit_end,
    held_start,
    learned_required,
    measured,
    paid_fraction,
    pairs,
    replay,
    score,
    score_learned,
    split_log,
    stalled,
    verdict,
    verdict_learned,
)

WINDOW = 10
WINDOW_PLUS_ONE = 11
FALL_OF_FOUR = 4
THREE_ENTRIES = 3
PAIRS_IN_LINT = 3
COUNT_IN_LINT = 6
SEVENTY = 70
SEVEN = 7
THIRTY = 30
TWENTY = 20
SHARE_OF_FALLING = 0.323
FLOOR_ONE = (3, 0.3, 1)
FLOOR_TWO = (3, 0.3, 2)
EPOCH = 1_700_000_000
BASELINE_TEXT = '{"a": {"as_written": "x", "stripped": "y"}, "b": {"as_written": "z"}}'
LINT_TEXT = '{"a.py": {"PLC0415": 3, "S404": 1}, "b.py": {"misc": 2}, "c.py": 5}'
SRC = ["src/nemik/a.py"]
LOG_TEXT = (
    f"@aaa {EPOCH}\nsrc/nemik/a.py\ndocs/b.md\n\n@bbb\n\n@ccc {EPOCH + 1}\nx.py\n"
)
FALLING = [100 - 2 * i for i in range(THIRTY)]
FLAT = [50] * THIRTY


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


def test_the_held_out_part_starts_at_seventy_percent_and_fitting_stops_early() -> None:
    """R462 and R464: 70 of 100 landings fit, and the last ten of those are embargoed."""
    assert held_start(100) == SEVENTY
    assert held_start(10) == SEVEN
    assert fit_end(SEVENTY) == SEVENTY - WINDOW
    assert fit_end(WINDOW - 1) == 0


def test_scoring_from_a_later_landing_scores_only_the_held_out_part() -> None:
    """Earlier landings still feed the windows, but only landings from `first` on are scored."""
    falling = [(f"s{i}", SRC, 30 - 2 * i) for i in range(WINDOW_PLUS_ONE)]
    flat = [(f"t{i}", SRC, 10) for i in range(WINDOW_PLUS_ONE)]
    landings = falling + flat
    everything = score(landings)["scored"]
    later = score(landings, CODON, WINDOW)["scored"]
    assert later == everything[WINDOW:]
    assert "s10" in later
    assert "s0" not in later


def test_the_paid_fraction_is_the_window_fall_over_the_value_it_started_from() -> None:
    """Twenty paid off 62 is about a third; too little history pays nothing."""
    assert round(paid_fraction(FALLING, THIRTY), 3) == SHARE_OF_FALLING
    assert not paid_fraction([5] * WINDOW, WINDOW)
    assert not paid_fraction([5, 9, 12, *([20] * WINDOW)], WINDOW + 3)


def test_a_flat_series_learns_the_minimum_rate_never_zero() -> None:
    """Nothing paid means a rate of zero, and the required fall is min_rate, not zero."""
    assert learned_required(FLAT, FLOOR_ONE) == FLOOR_ONE[2]
    assert learned_required(FLAT, FLOOR_TWO) == FLOOR_TWO[2]


def test_a_series_that_pays_is_ok_and_one_that_stops_is_behind() -> None:
    """The learned required fall is a share of the value, so a steady payer clears it."""
    assert verdict_learned(FALLING, FLOOR_ONE) == "ok"
    assert verdict_learned(FLAT, FLOOR_ONE) == "behind"


def test_scoring_a_flat_series_finds_no_error_and_scores_every_judged_landing() -> None:
    """MUTANT: a rule that said ok on a flat series would be a false ok on a stalled one."""
    flat = [(f"s{i}", SRC, 10) for i in range(THIRTY)]
    assert score_learned(flat, CODON, FLOOR_ONE, (0, THIRTY)) == (0, 0, TWENTY)
    assert fit(flat, CODON, TWENTY) == GRID[0]
