# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pace_replay judges a ratchet's window under the current and the proposed rule (nemik:W2020)."""

from pace_replay import (
    BOUNDS,
    CODON,
    GRID,
    MGRID,
    MYPY,
    QGRID,
    RUFF,
    admission,
    bounded_blocks,
    counts,
    days_to_zero,
    entries,
    fall,
    fit,
    fit_bound,
    fit_end,
    fit_median,
    fit_quantile,
    held_start,
    landings_to_zero,
    learned_required,
    learned_wait,
    measured,
    median_required,
    neglected_rows,
    neglected_share,
    paid_fraction,
    pairs,
    quantile_required,
    replay,
    rose,
    row_ages,
    row_gaps,
    row_series,
    row_values,
    score,
    score_admission,
    score_blocks,
    score_learned,
    score_neglect,
    split_log,
    stalled,
    stalled_rows,
    trajectory,
    verdict,
    verdict_learned,
)

WINDOW = 10
A_ROW = "src/nemik/a.py"
B_ROW = "src/nemik/b.py"
HALF_AS_MANY = [60 - at // 2 for at in range(40)]
TOTALS = [a + 5 for a in HALF_AS_MANY]
TWO_ROWS = {A_ROW: HALF_AS_MANY, B_ROW: [5] * 40}
NEGLECTED = neglected_rows(TWO_ROWS, 50)
TOUCHES_A = [(f"s{at}", [A_ROW], total) for at, total in enumerate(TOTALS)]
TOUCHES_BOTH = [(f"s{at}", [A_ROW, B_ROW], total) for at, total in enumerate(TOTALS)]
SCORED_A = score_neglect(TOUCHES_A, NEGLECTED, CODON, (0, 40))
SCORED_BOTH = score_neglect(TOUCHES_BOTH, NEGLECTED, CODON, (0, 40))
SHARES = neglected_share(TWO_ROWS, NEGLECTED)
BLOCKS_AT_ZERO = bounded_blocks(TOUCHES_A, NEGLECTED, SHARES, BOUNDS[0])
BLOCKS_AT_HALF = bounded_blocks(TOUCHES_A, NEGLECTED, SHARES, 50)
BLOCKS_BOTH = bounded_blocks(TOUCHES_BOTH, NEGLECTED, SHARES, BOUNDS[0])
SCORED_BLOCKS = score_blocks(TOUCHES_A, BLOCKS_AT_ZERO, CODON, (0, 40))
BY_PERCENT = dict.fromkeys((50, 75, 90), (NEGLECTED, SHARES))
FITTED = fit_bound(TOUCHES_A, BY_PERCENT, CODON, 30)
TRAJECTORY_TEXT = trajectory(TOUCHES_A, BLOCKS_AT_ZERO, SHARES, (10, 30))
STEPS = [3, 3, 2, 2, 2, 1]
STEP_GAPS = row_gaps(STEPS)
STEP_AGES = row_ages(STEPS)
EARLY_WAIT = learned_wait(STEP_GAPS, 1, 50)
LATER_WAIT = learned_wait(STEP_GAPS, 5, 50)
FIVE_TO_ZERO = landings_to_zero([10, 9, 8, 7, 6, 5], 0)
ROWS_TEXT = '{"a.py": {"X": 3, "Y": 1}, "b.py": {"X": 2}, "c.py": 5}'
ROW_COUNTS = row_values(ROWS_TEXT, "counts")
ROW_ENTRIES = row_values(ROWS_TEXT, "pairs")
ROW_AFTER = [{"a.py": 4}, {"a.py": 3, "b.py": 2}, {"b.py": 2}]
ROW_SERIES = row_series(ROW_AFTER)
PAYER_AND_STALLER = row_series(
    [{"a.py": 30 - i, "b.py": 5} for i in range(WINDOW + WINDOW)]
)
STALLED_AT_END = stalled_rows(PAYER_AND_STALLER, WINDOW + WINDOW - 1)
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
QUANTILE = (5, 25, 1)
MEDIAN = (5, 1)
EPOCH = 1_700_000_000
DAY = 86400
BASELINE_TEXT = '{"a": {"as_written": "x", "stripped": "y"}, "b": {"as_written": "z"}}'
LINT_TEXT = '{"a.py": {"PLC0415": 3, "S404": 1}, "b.py": {"misc": 2}, "c.py": 5}'
SRC = ["src/nemik/a.py"]
LOG_TEXT = (
    f"@aaa {EPOCH}\nsrc/nemik/a.py\ndocs/b.md\n\n@bbb\n\n@ccc {EPOCH + 1}\nx.py\n"
)
FALLING = [100 - 2 * i for i in range(THIRTY)]
FLAT = [50] * THIRTY
SPAN = (0, THIRTY)
REQUIRED = [1] * THIRTY
ONE_FALSE_BEHIND = (0, 1, 1)
NO_ERROR = (0, 0, TWENTY)
FIFTY = 50


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
    assert score_learned(flat, CODON, FLOOR_ONE, SPAN) == NO_ERROR
    assert fit(flat, CODON, TWENTY) == GRID[0]


def test_the_quantile_required_fall_never_falls_and_a_stall_does_not_lower_it() -> None:
    """github-14's point 1: paying windows only, ratcheted upward; a flat tail leaves it alone."""
    required = quantile_required(FALLING + [FALLING[-1]] * THIRTY, QUANTILE)
    assert required == sorted(required)
    assert required[-1] == required[THIRTY]
    assert required[-1] > QUANTILE[2]


def test_a_series_that_never_pays_keeps_the_minimum_rate() -> None:
    """MUTANT: a rule that learned from stalled windows would drift to zero; this one stays put."""
    assert set(quantile_required(FLAT, QUANTILE)) == {QUANTILE[2]}


def test_a_rise_within_ten_measured_landings_is_seen() -> None:
    """Honest discovery raises the value; the replay must not count it against a rule."""
    landings = [(f"s{i}", SRC, 10 if i < WINDOW else 12) for i in range(THIRTY)]
    assert rose(landings, 0, CODON)
    flat = [(f"s{i}", SRC, 10) for i in range(THIRTY)]
    assert not rose(flat, 0, CODON)


def test_each_rule_names_the_admission_of_a_landing_that_pays_nothing() -> None:
    """`current` and `window` read their own series; `learned` reads the required fall."""
    paying = [9, *([5] * WINDOW)]
    assert admission("current", paying, [], 1) == "ok"
    assert admission("window", [], paying, 1) == "ok"
    assert admission("window", paying, [], 1) == "behind"
    assert admission("learned", paying, [], FALL_OF_FOUR) == "ok"
    assert admission("learned", paying, [], FALL_OF_FOUR + 1) == "behind"


def test_only_a_landing_that_paid_nothing_is_scored_as_an_admission() -> None:
    """A landing that lowers the value is always admitted, so it can be neither error."""
    falling = [(f"s{i}", SRC, 100 - 2 * i) for i in range(THIRTY)]
    flat = [(f"s{i}", SRC, 10) for i in range(THIRTY)]
    first = score_admission(falling, CODON, "current", REQUIRED, SPAN)
    second = score_admission(flat, CODON, "current", REQUIRED, SPAN)
    assert first == ONE_FALSE_BEHIND
    assert second == NO_ERROR


def test_the_quantile_fit_is_deterministic_on_a_flat_series() -> None:
    """With no error anywhere on the grid, the first grid point is chosen."""
    flat = [(f"s{i}", SRC, 10) for i in range(THIRTY)]
    assert fit_quantile(flat, CODON, TWENTY) == QGRID[0]


def test_the_median_required_fall_does_not_move_on_a_stall() -> None:
    """A stall adds no paying window, so the median stays where the last payer left it."""
    required = median_required(FALLING + [FALLING[-1]] * THIRTY, MEDIAN)
    assert required[-1] == required[THIRTY + WINDOW]
    assert required[-1] > MEDIAN[1]


def test_the_median_can_fall_when_the_paying_windows_shrink() -> None:
    """MUTANT: unlike the never-falling quantile, a median follows the repo's recent payers down."""
    big = [2000 - 100 * i for i in range(WINDOW + WINDOW)]
    small = [big[-1] - i for i in range(1, THIRTY)]
    required = median_required([*big, *small], (3, 1))
    assert required[-1] < max(required)


def test_a_series_that_never_pays_keeps_the_median_floor() -> None:
    """MUTANT: a median that learned from stalled windows would drift to zero."""
    assert set(median_required(FLAT, MEDIAN)) == {MEDIAN[1]}


def test_the_median_fit_is_deterministic_on_a_flat_series() -> None:
    """With no error anywhere on the grid, the first grid point is chosen."""
    flat = [(f"s{i}", SRC, 10) for i in range(THIRTY)]
    assert fit_median(flat, CODON, TWENTY) == MGRID[0]


def test_days_to_zero_is_the_value_over_the_historical_rate() -> None:
    """Two a day over 38 days fell 38; the 62 left need 62 days at that rate."""
    epochs = [EPOCH + DAY * 2 * i for i in range(TWENTY)]
    values = [100 - 2 * i for i in range(TWENTY)]
    assert round(days_to_zero(epochs, values, 0)) == values[-1]
    assert days_to_zero(epochs, [FIFTY] * TWENTY, 0) < 0
    assert days_to_zero([EPOCH] * TWENTY, values, 0) < 0


def test_a_row_ages_from_its_last_fall_or_from_its_appearance() -> None:
    """A row that never fell is aged from where it appeared, so an untouched row has an age."""
    assert STEP_AGES == [0, 1, 0, 1, 2, 0]
    assert row_ages([0, 0, 4, 4, 4]) == [0, 1, 0, 1, 2]
    assert row_ages([7] * THIRTY)[-1] == THIRTY - 1


def test_a_wait_is_completed_by_a_fall_since_the_previous_fall_or_birth() -> None:
    """Each fall completes one wait; the first runs from the row's appearance."""
    assert STEP_GAPS == [(2, 2), (5, 3)]


def test_the_learned_wait_needs_a_completed_wait_and_grows_with_history() -> None:
    """MUTANT: a rule with a constant N would not change; none completed yet means -1."""
    assert EARLY_WAIT == -1
    assert LATER_WAIT == THREE_ENTRIES


def test_only_a_row_nobody_pays_is_neglected() -> None:
    """The payer's age never passes its own wait; the untouched row's age does."""
    assert NEGLECTED[1] == []
    assert NEGLECTED[2] == []
    assert NEGLECTED[THREE_ENTRIES] == [B_ROW]


def test_touching_a_neglected_row_is_the_way_out() -> None:
    """MUTANT: a rule that blocked every stack would refuse the one touching the neglected row."""
    assert SCORED_A[1] > 0
    assert SCORED_BOTH[1] == 0
    assert SCORED_A[2] == SCORED_BOTH[2]


def test_landings_to_zero_is_the_value_over_the_rate_per_landing() -> None:
    """Five fell in five landings, so the five left need five more; no fall gives -1."""
    assert round(FIVE_TO_ZERO) == WINDOW // 2
    assert landings_to_zero([4] * THIRTY, 0) < 0


def test_the_neglected_share_is_neglected_rows_over_owing_rows() -> None:
    """Nothing is neglected before the first wait completes; then one of the two owing rows is."""
    assert round(SHARES[1] * 100) == 0
    assert round(SHARES[THREE_ENTRIES] * 100) == FIFTY


def test_a_share_above_the_bound_refuses_a_stack_touching_no_neglected_row() -> None:
    """MUTANT: a bound of zero refuses such landings; a bound at the share refuses none."""
    assert any(BLOCKS_AT_ZERO)
    assert not any(BLOCKS_AT_HALF)
    assert not any(BLOCKS_BOTH)


def test_scoring_blocks_agrees_with_scoring_neglect_at_a_bound_of_zero() -> None:
    """A bound of zero is the unbounded rule, so the two scorers must agree."""
    assert SCORED_BLOCKS == SCORED_A


def test_the_fitted_bound_is_the_first_grid_point_with_no_error() -> None:
    """The first percentile, and the lowest bound that refuses nothing wrongly."""
    assert FITTED == (FIFTY, FIFTY)


def test_the_trajectory_names_refusals_and_what_paying_landings_paid() -> None:
    """Ten landings that paid nothing were refused; ten paid one each; the share never cleared."""
    assert "refused (paid nothing) 10" in TRAJECTORY_TEXT
    assert "never" in TRAJECTORY_TEXT
    assert "total fall 10" in TRAJECTORY_TEXT


def test_a_row_is_valued_as_its_counts_or_its_entries() -> None:
    """A file's value is the sum of its rule counts, or its number of rules; a bare number is 0."""
    assert ROW_COUNTS == {"a.py": 4, "b.py": 2, "c.py": 0}
    assert ROW_ENTRIES == {"a.py": 2, "b.py": 1, "c.py": 0}
    assert row_values("not json", "counts") == {}


def test_a_row_not_there_yet_or_gone_is_zero_in_its_series() -> None:
    """The series of a file has one value per landing, zero before it appears and after it goes."""
    assert ROW_SERIES == {"a.py": [4, 3, 0], "b.py": [0, 2, 2]}


def test_only_the_row_that_stands_still_is_stalled() -> None:
    """MUTANT: a repo that pays the cheapest row forever is stalled on every other row."""
    assert STALLED_AT_END == ["b.py"]
    assert stalled_rows({"z.py": [0] * (WINDOW + WINDOW)}, WINDOW + WINDOW - 1) == []
