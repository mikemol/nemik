# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1064: what a publish build cost, as gauges, so the builder's memory is a series.

The builder runs nemik-serve --publish as a fresh process on every pass, so a process's peak
resident set is the cost of one build, not growth with uptime. luthen-observability's OOM reading
(W1651) asked whether the memory grows or is a function of the input; reading it from the cgroup
shows the climb, and this shows the build's own peak and CPU on every build.

nemik:W1074: under a memory limit the resident peak saturates at the limit, the excess going to
swap (github-8f), so the demand is the resident peak plus what was swapped. The gauges therefore
carry the process's swapped bytes and the container cgroup's own peak and swap peak, and every
sample is labelled with the pod and whether the build started from a restored cache, so a warm build
reads alone from the store. Plain strings and integers only, no import, so the Codon census
compiles it.
"""

GAUGE_PEAK = "nemik_build_peak_rss_bytes"
GAUGE_SWAP = "nemik_build_swap_bytes"
GAUGE_CGROUP_PEAK = "nemik_build_cgroup_peak_bytes"
GAUGE_CGROUP_SWAP_PEAK = "nemik_build_cgroup_swap_peak_bytes"
GAUGE_CPU = "nemik_build_cpu_seconds"
KIB = 1024
FIELDS = 2  # a status line is a name and a value


def kib_of(status: str, field: str) -> int:
    """Read one kibibyte field out of the kernel's status text.

    Args:
        status: The text of /proc/<pid>/status.
        field: The line's name with its colon, such as VmHWM: or VmSwap:.

    Returns:
        The field's value in KiB, or 0 when there is no such line (a kernel without it, or a
        process that is not Linux's) or its value is not a number, so a build still publishes a
        gauge.

    """
    for line in status.splitlines():
        if line.startswith(field):
            words = line.split()
            if len(words) >= FIELDS and words[1].isdigit():
                return int(words[1])
    return 0


def peak_kib_of(status: str) -> int:
    """Read a process's peak resident set out of the kernel's status text.

    Args:
        status: The text of /proc/<pid>/status.

    Returns:
        The VmHWM line's value in KiB, or 0 when there is none.

    """
    return kib_of(status, "VmHWM:")


def swap_kib_of(status: str) -> int:
    """Read what a process has swapped out, from the kernel's status text.

    Args:
        status: The text of /proc/<pid>/status.

    Returns:
        The VmSwap line's value in KiB, or 0 when there is none.

    """
    return kib_of(status, "VmSwap:")


def bytes_of(text: str) -> int:
    """Read a cgroup file that holds one number of bytes, such as memory.peak.

    Args:
        text: The file's text.

    Returns:
        The number, or 0 when the file is absent (empty text) or holds something else (max).

    """
    word = text.strip()
    return int(word) if word.isdigit() else 0


def labels_of(pod: str, cache_hit: int) -> str:
    """Write the label set every build gauge carries.

    Args:
        pod: The pod's name, empty when not known.
        cache_hit: 1 when the build started from a restored cache, else 0.

    Returns:
        The label text, braces included.

    """
    return f'{{pod="{pod}",cache_hit="{cache_hit}"}}'


def build_cost_lines(
    peak_kib: int, swap_kib: int, cgroup: tuple[int, int], cpu_ms: int, labels: str
) -> list[str]:
    """Write the gauges of a build, Prometheus text.

    Args:
        peak_kib: The process's peak resident set so far, in KiB (VmHWM).
        swap_kib: What the process has swapped out, in KiB (VmSwap).
        cgroup: The container's memory.peak and memory.swap.peak, in bytes; 0 when unreadable.
        cpu_ms: The CPU time the process has used, user and system together, in milliseconds.
        labels: The label text from labels_of.

    Returns:
        A TYPE line and one sample per gauge: the peaks and the swap in bytes, the CPU in seconds.

    """
    return [
        f"# TYPE {GAUGE_PEAK} gauge",
        f"{GAUGE_PEAK}{labels} {peak_kib * KIB}",
        f"# TYPE {GAUGE_SWAP} gauge",
        f"{GAUGE_SWAP}{labels} {swap_kib * KIB}",
        f"# TYPE {GAUGE_CGROUP_PEAK} gauge",
        f"{GAUGE_CGROUP_PEAK}{labels} {cgroup[0]}",
        f"# TYPE {GAUGE_CGROUP_SWAP_PEAK} gauge",
        f"{GAUGE_CGROUP_SWAP_PEAK}{labels} {cgroup[1]}",
        f"# TYPE {GAUGE_CPU} gauge",
        f"{GAUGE_CPU}{labels} {cpu_ms / 1000:.3f}",
    ]
