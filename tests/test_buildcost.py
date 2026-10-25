# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1064: a build's peak memory and CPU are published as two gauges."""

from nemik.buildcost import build_cost_lines, peak_kib_of

PEAK_KIB = 1055216
STATUS = (
    "Name:\tpython3\nVmPeak:\t 2000000 kB\nVmHWM:\t 1055216 kB\nVmRSS:\t 900000 kB\n"
)


def test_the_peak_is_in_bytes_and_the_cpu_in_seconds() -> None:
    """The measured cold build: 1,055,216 KiB peak and 275.72 s CPU."""
    assert build_cost_lines(1055216, 275720) == [
        "# TYPE nemik_build_peak_rss_bytes gauge",
        "nemik_build_peak_rss_bytes 1080541184",
        "# TYPE nemik_build_cpu_seconds gauge",
        "nemik_build_cpu_seconds 275.720",
    ]


def test_a_build_that_used_nothing_still_publishes_both() -> None:
    """Zero is a reading, not an absence."""
    lines = build_cost_lines(0, 0)
    assert "nemik_build_peak_rss_bytes 0" in lines
    assert "nemik_build_cpu_seconds 0.000" in lines


def test_the_peak_is_read_from_the_high_water_line_not_the_current_one() -> None:
    """VmHWM is the peak; VmRSS and VmPeak are other things."""
    assert peak_kib_of(STATUS) == PEAK_KIB


def test_a_status_without_the_line_reads_as_zero_not_an_error() -> None:
    """No VmHWM, an empty text, or a value that is not a number: 0, so the gauge is still there."""
    assert peak_kib_of("Name:\tpython3\n") == 0
    assert peak_kib_of("") == 0
    assert peak_kib_of("VmHWM:\t lots kB\n") == 0
