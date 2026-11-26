# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2517: the builder counts its publish passes by outcome, built or skipped.

The builder runs `nemik-serve --publish` as a fresh process on every pass (about every 30 s), and
a pass whose fleet is unchanged builds nothing and exits. The build gauges (buildcost) are written
into a snapshot only by a BUILD, so a skipped pass left no trace and the store could not say what
share of passes build, nor what a skipped pass costs against a built one (nemik:W1020). A counter
cannot live in a process that lives one pass, so the totals ride a small file beside the snapshots
(`passes`, two lines), every pass adds one to its outcome, and the lines below are what /metrics
carries: `nemik_publish_passes_total{outcome="built|skipped",pod}`, a Prometheus counter. A counter
that resets (a lost volume) is a reset to rate(), not an error.

Plain strings and integers only, no import, so the Codon census compiles it.
"""

COUNTER = "nemik_publish_passes_total"
BUILT = "built"
SKIPPED = "skipped"
OUTCOMES = [BUILT, SKIPPED]
HELP = (
    "publish passes by outcome since the counts file was made: built (the fleet changed and a "
    "snapshot was published) or skipped (nothing changed; the pass exited after its hash check)"
)

Counts = tuple[int, int]


def parse(text: str) -> Counts:
    """Read the counts file.

    Args:
        text: The file's text, `built <n>` and `skipped <n>` lines, or "" when there is none.

    Returns:
        (built, skipped). A missing or unreadable line counts 0, so a lost or damaged file starts a
        counter over (which rate() reads as a reset) and never stops a pass.

    """
    got = {BUILT: 0, SKIPPED: 0}
    for line in text.splitlines():
        words = line.split()
        if len(words) == len(OUTCOMES) and words[0] in got and words[1].isdigit():
            got[words[0]] = int(words[1])
    return got[BUILT], got[SKIPPED]


def render(counts: Counts) -> str:
    """Write the counts file.

    Returns:
        The two lines `built <n>` and `skipped <n>`.

    """
    return f"{BUILT} {counts[0]}\n{SKIPPED} {counts[1]}\n"


def bump(counts: Counts, outcome: str) -> Counts:
    """Count one pass.

    Args:
        counts: (built, skipped) so far.
        outcome: BUILT or SKIPPED.

    Returns:
        The counts with that outcome one higher.

    Raises:
        ValueError: when the outcome is neither, a defect in the caller and never a count.

    """
    if outcome == BUILT:
        return counts[0] + 1, counts[1]
    if outcome == SKIPPED:
        return counts[0], counts[1] + 1
    msg = f"not a pass outcome: {outcome!r}"
    raise ValueError(msg)


def lines(counts: Counts, pod: str) -> list[str]:
    """Write the counter as Prometheus text.

    Args:
        counts: (built, skipped).
        pod: The pod's name, empty when not known.

    Returns:
        A HELP and a TYPE line, then one sample per outcome, both outcomes always present.

    """
    return [
        f"# HELP {COUNTER} {HELP}",
        f"# TYPE {COUNTER} counter",
        f'{COUNTER}{{outcome="{BUILT}",pod="{pod}"}} {counts[0]}',
        f'{COUNTER}{{outcome="{SKIPPED}",pod="{pod}"}} {counts[1]}',
    ]


def merge(metrics: str, counter_lines: list[str]) -> str:
    """Put the counter into a /metrics text, replacing any earlier one.

    Args:
        metrics: The metrics file's text, possibly with an earlier copy of the counter.
        counter_lines: The lines from `lines`.

    Returns:
        The text without any earlier counter line, then the new lines, ending in one newline.

    """
    kept = [line for line in metrics.splitlines() if COUNTER not in line]
    return "\n".join([*kept, *counter_lines]) + "\n"
