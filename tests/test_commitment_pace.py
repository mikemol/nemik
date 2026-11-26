# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1007: the commitment census, resampled onto the landing clock and judged by the pace."""

import json

from nemik import commitmentpace as cp
from nemik.ratchetpace import WINDOW

PERIOD = 900_000  # a census period in the planted series, milliseconds
GAP = 10  # the steady gap of the small period test
LEVEL = 9  # a steady open count
DARK_FROM, DARK_TO = 10, 25  # the census indexes with no sample in the recovered series
EARLY = 2  # an index early in the stopped-layer series
START = 1_000_000_000_000


def _census(count_at: dict[int, int]) -> list[tuple[int, int]]:
    # one layer's samples: (time, count), the periods keyed by their index
    return [
        (START + index * PERIOD, count) for index, count in sorted(count_at.items())
    ]


def _steady(counts: list[int]) -> list[tuple[int, int]]:
    # a census that never missed a period
    return _census(dict(enumerate(counts)))


def test_the_census_period_is_the_median_gap() -> None:
    """One slow gap does not move the median; fewer than two samples have no period."""
    times = [0, GAP, 2 * GAP, 3 * GAP, 50 * GAP, 51 * GAP]
    assert cp.census_period(times) == GAP
    assert cp.census_period([7]) == cp.NO_PERIOD
    assert cp.census_period([]) == cp.NO_PERIOD


def test_a_landing_reads_the_latest_fresh_sample_and_sums_the_layers() -> None:
    """Each layer's newest sample at or before the landing counts; the layers add."""
    one = _steady([5, 6, 7, 8])
    two = _steady([1, 1, 2, 2])
    when = START + 2 * PERIOD + 1000
    assert cp.at_landing([one, two], when) == 7 + 2


def test_a_stale_sample_is_not_carried_forward() -> None:
    """Older than STALE_PERIODS census periods reads UNMEASURED, never the old count."""
    samples = _steady([LEVEL] * 4)
    edge = START + 3 * PERIOD + cp.STALE_PERIODS * PERIOD
    assert cp.at_landing([samples], edge) == LEVEL
    assert cp.at_landing([samples], edge + 1) == cp.UNMEASURED


def test_a_landing_before_any_sample_or_with_no_census_is_unmeasured_not_zero() -> None:
    """Empty is not zero: no sample at or before, or no layers at all, is UNMEASURED."""
    samples = _steady([3, 3, 3])
    assert cp.at_landing([samples], START - 1) == cp.UNMEASURED
    assert cp.at_landing([], START) == cp.UNMEASURED
    assert cp.at_landing([[]], START) == cp.UNMEASURED


def _landings(count: int) -> list[int]:
    # one landing per census period
    return [START + i * PERIOD for i in range(count)]


def _points(counts: list[int]) -> list[int]:
    # the series resampled with a landing per period, so it never went dark
    return cp.resample([_steady(counts)], _landings(len(counts)))


def test_a_rising_series_reads_behind() -> None:
    """Open commitments that grow over the window owe a paydown and show none."""
    state, fell, owed = cp.judge(_points(list(range(10, 10 + 4 * WINDOW))), WINDOW, 0)
    assert (state, owed) == ("behind", 1)
    assert fell < 0


def test_a_falling_series_reads_ok() -> None:
    """A series falling one a landing pays what its own earlier windows owed."""
    counts = list(range(6 * WINDOW + 20, 20, -1))
    state, fell, owed = cp.judge(_points(counts), WINDOW, 0)
    assert state == "ok"
    assert fell == WINDOW
    assert owed == WINDOW


def test_an_empty_store_is_unknown() -> None:
    """No landings resampled at all, or no census: UNKNOWN, with nothing owed or observed."""
    assert cp.judge([], WINDOW, 0) == ("unknown", 0, 0)
    dark = cp.resample([], _landings(2 * WINDOW))
    assert set(dark) == {cp.UNMEASURED}
    assert cp.judge(dark, WINDOW, 0) == ("unknown", 0, 0)


def test_a_census_that_went_dark_inside_the_window_is_unknown() -> None:
    """A stretch of landings with no fresh sample puts UNMEASURED points in the window."""
    census = _steady(list(range(40, 20, -1)))
    # landings keep coming long after the census stopped at index 19
    points = cp.resample([census], _landings(20 + 2 * cp.STALE_PERIODS + 4))
    assert points[-1] == cp.UNMEASURED
    assert cp.judge(points, WINDOW, 0) == ("unknown", 0, 0)


def test_a_dark_stretch_long_ago_leaves_a_shorter_history_not_an_invented_one() -> None:
    """After the census recovers, the verdict reads the measured run only."""
    counts = list(range(60, 0, -1))
    census = _census(
        {i: c for i, c in enumerate(counts) if not DARK_FROM <= i < DARK_TO}
    )
    points = cp.resample([census], _landings(len(counts)))
    assert cp.UNMEASURED in points
    state, _, _ = cp.judge(points, WINDOW, 0)
    assert state == "ok"


def _line(metric: dict[str, str], samples: list[tuple[int, int]]) -> str:
    # one line of the store's raw export
    document: dict[str, object] = {
        "metric": metric,
        "values": [count for _, count in samples],
        "timestamps": [when for when, _ in samples],
    }
    return json.dumps(document)


def test_the_export_is_read_into_layers_and_landings_then_resampled() -> None:
    """The census family and the landed ratchet samples give one repo its landing-clock points."""
    census = {"__name__": cp.NAME, "repo": "nemik", "layer": "none"}
    memory = {"__name__": cp.NAME, "repo": "nemik", "layer": "memory"}
    other = {"__name__": cp.NAME, "repo": "luthen", "layer": "none"}
    landed = {
        "__name__": "mikemol.ratchet.value",
        "repo": "nemik",
        "ratchet": "ruff-baseline.json",
        "stage": cp.LANDED,
    }
    text = "\n".join(
        [
            _line(census, _steady([10, 9, 8])),
            _line(memory, _steady([2, 2, 2])),
            _line(other, _steady([4])),
            _line(landed, [(START, 1), (START + 2 * PERIOD, 1)]),
            "not json",
            "",
        ]
    )
    assert sorted(cp.commitment_layers(text)) == ["luthen", "nemik"]
    assert cp.landing_times(text) == {"nemik": [START, START + 2 * PERIOD]}
    # luthen has a census but no landing, so it has no points; nemik reads 10+2 then 8+2
    assert cp.commitment_points(text) == {"nemik": [12, 10]}


def test_a_stopped_layer_beside_a_fresh_one_makes_the_landing_unmeasured() -> None:
    """Stopped emitting and reached zero look alike, so a stale layer is never counted as zero."""
    live = _steady(list(range(20)))
    stopped = _steady([3, 3, 3])
    early = START + EARLY * PERIOD
    late = START + 10 * PERIOD
    assert cp.at_landing([live, stopped], early) == EARLY + 3
    assert cp.at_landing([live, stopped], late) == cp.UNMEASURED
    # a layer that has not begun yet is not stale, it is simply not there
    assert cp.at_landing([live, _census({15: 4})], early) == EARLY


def test_a_negative_count_is_corrupt_unmeasured_and_named() -> None:
    """A negative open count is bad data: its landing reads UNMEASURED and the line is named."""
    census = {"__name__": cp.NAME, "repo": "nemik", "layer": "none"}
    landed = {
        "__name__": cp.RATCHET_FAMILY,
        "repo": "nemik",
        "ratchet": "x",
        "stage": cp.LANDED,
    }
    text = "\n".join(
        [
            _line(census, _steady([5, -3, 4])),
            _line(landed, [(START, 1), (START + PERIOD, 1), (START + 2 * PERIOD, 1)]),
        ]
    )
    assert cp.commitment_points(text) == {"nemik": [5, cp.UNMEASURED, 4]}
    assert cp.corrupt(text) == [f"nemik none at {START + PERIOD}"]


def test_only_the_ratchet_family_sets_the_landing_clock() -> None:
    """A foreign family that reuses stage=landed adds no landings."""
    foreign = {"__name__": "mikemol.other.value", "repo": "nemik", "stage": cp.LANDED}
    assert cp.landing_times(_line(foreign, [(START, 1)])) == {}
