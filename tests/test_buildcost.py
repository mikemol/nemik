# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1064, W1074: a build's memory and CPU are gauges, labelled by pod and by cache."""

from nemik.buildcost import (
    build_cost_lines,
    bytes_of,
    labels_of,
    peak_kib_of,
    swap_kib_of,
)

PEAK_KIB = 1055216
SWAP_KIB = 341504
CGROUP_PEAK = 940000000
CGROUP_SWAP = 333700000
STATUS = (
    "Name:\tpython3\nVmPeak:\t 2000000 kB\nVmHWM:\t 1055216 kB\nVmRSS:\t 900000 kB\n"
    "VmSwap:\t 341504 kB\n"
)
LABELS = '{pod="nemik-x",cache_hit="1"}'


def test_the_gauges_carry_resident_swap_cgroup_and_cpu_with_labels() -> None:
    """The measured cold build's 1,055,216 KiB peak and 275.72 s CPU, with a swap and a cgroup."""
    peaks = (CGROUP_PEAK, CGROUP_SWAP)
    got = build_cost_lines(PEAK_KIB, SWAP_KIB, peaks, 275720, LABELS)
    assert got == [
        "# TYPE nemik_build_peak_rss_bytes gauge",
        f"nemik_build_peak_rss_bytes{LABELS} 1080541184",
        "# TYPE nemik_build_swap_bytes gauge",
        f"nemik_build_swap_bytes{LABELS} 349700096",
        "# TYPE nemik_build_cgroup_peak_bytes gauge",
        f"nemik_build_cgroup_peak_bytes{LABELS} {CGROUP_PEAK}",
        "# TYPE nemik_build_cgroup_swap_peak_bytes gauge",
        f"nemik_build_cgroup_swap_peak_bytes{LABELS} {CGROUP_SWAP}",
        "# TYPE nemik_build_cpu_seconds gauge",
        f"nemik_build_cpu_seconds{LABELS} 275.720",
    ]


def test_a_build_that_used_nothing_still_publishes_every_gauge() -> None:
    """Zero is a reading, not an absence."""
    lines = build_cost_lines(0, 0, (0, 0), 0, LABELS)
    assert f"nemik_build_peak_rss_bytes{LABELS} 0" in lines
    assert f"nemik_build_swap_bytes{LABELS} 0" in lines
    assert f"nemik_build_cpu_seconds{LABELS} 0.000" in lines


def test_the_labels_name_the_pod_and_whether_the_build_started_warm() -> None:
    """A pod name and a 0 or 1 make one build readable alone from the store."""
    assert labels_of("nemik-x", 1) == LABELS
    assert labels_of("", 0) == '{pod="",cache_hit="0"}'


def test_the_peak_is_read_from_the_high_water_line_not_the_current_one() -> None:
    """VmHWM is the peak; VmRSS and VmPeak are other things."""
    assert peak_kib_of(STATUS) == PEAK_KIB


def test_the_swap_is_read_from_its_own_line() -> None:
    """VmSwap is what the process has swapped out."""
    assert swap_kib_of(STATUS) == SWAP_KIB


def test_a_status_without_the_line_reads_as_zero_not_an_error() -> None:
    """No VmHWM, an empty text, or a value that is not a number: 0, so the gauge is still there."""
    assert peak_kib_of("Name:\tpython3\n") == 0
    assert peak_kib_of("") == 0
    assert peak_kib_of("VmHWM:\t lots kB\n") == 0
    assert swap_kib_of("Name:\tpython3\n") == 0


def test_a_cgroup_file_reads_as_its_number_and_anything_else_as_zero() -> None:
    """memory.peak holds a number; an absent file (empty text) or max reads 0."""
    assert bytes_of(f"{CGROUP_PEAK}\n") == CGROUP_PEAK
    assert bytes_of("") == 0
    assert bytes_of("max\n") == 0
