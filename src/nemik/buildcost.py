# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1064: what a publish build cost, as gauges, so the builder's memory is a series.

The builder runs nemik-serve --publish as a fresh process on every pass, so a process's peak
resident set is the cost of one build, not growth with uptime. luthen-observability's OOM reading
(W1651) asked whether the memory grows or is a function of the input; reading it from the cgroup
shows the climb, and this shows the build's own peak and CPU on every build. Plain strings and
integers only, no import, so the Codon census compiles it.
"""

GAUGE_PEAK = "nemik_build_peak_rss_bytes"
GAUGE_CPU = "nemik_build_cpu_seconds"
KIB = 1024
FIELDS = 2  # a status line is a name and a value


def peak_kib_of(status: str) -> int:
    """Read a process's peak resident set out of the kernel's status text.

    Args:
        status: The text of /proc/<pid>/status.

    Returns:
        The VmHWM line's value in KiB, or 0 when there is no such line (a kernel without it, or a
        process that is not Linux's), so a build still publishes a gauge.

    """
    for line in status.splitlines():
        if line.startswith("VmHWM:"):
            words = line.split()
            if len(words) >= FIELDS and words[1].isdigit():
                return int(words[1])
    return 0


def build_cost_lines(peak_kib: int, cpu_ms: int) -> list[str]:
    """Write the two gauges of a build, Prometheus text.

    Args:
        peak_kib: The process's peak resident set so far, in KiB, as getrusage's ru_maxrss gives it
            on Linux.
        cpu_ms: The CPU time the process has used, user and system together, in milliseconds.

    Returns:
        A TYPE line and one sample per gauge: the peak in bytes, the CPU in seconds.

    """
    return [
        f"# TYPE {GAUGE_PEAK} gauge",
        f"{GAUGE_PEAK} {peak_kib * KIB}",
        f"# TYPE {GAUGE_CPU} gauge",
        f"{GAUGE_CPU} {cpu_ms / 1000:.3f}",
    ]
