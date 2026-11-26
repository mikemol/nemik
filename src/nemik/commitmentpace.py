# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1007: the open-commitment count per repo as a ratchet, on the pace's own clock.

luthen's census emits `mikemol.commitments.open{repo, layer}` every census period (15 minutes in
practice). The pace judges a ratchet per LANDING (ratchetpace: WINDOW landings), and the operator's
rule is to forecast by throughput, not by the wall clock, so the clock-sampled series is RESAMPLED
onto the repo's landing clock (github-82's ruling on nemik:W1007): for each landing, each layer's
latest sample at or before it, the layers summed. Rules that keep that honest:

- A sample older than STALE_PERIODS census periods is not carried forward. The census period is
  read from the series itself (the median gap between its samples), so the bound is a count of
  producer periods, not a wall-clock literal.
- A landing where any layer that had begun is stale is UNMEASURED, and so is one where no layer
  has a sample: "stopped emitting" and "reached zero" look alike, and absence is never zero. The
  producer fix is an explicit 0 per layer. A layer retired for good belongs to the ended-series
  rule (stage 2), not to staleness.
- A negative count is corrupt data: that point is UNMEASURED and `corrupt` names the line.
- The landing clock is the `stage=landed` samples of mikemol.ratchet.value only.
- A verdict whose window holds an UNMEASURED point is UNKNOWN, never ok and never behind.

Sentinel ints (UNMEASURED, NO_SAMPLE, NO_PERIOD, NO_DARK) stand in for a maybe-result. That is a
deliberate exception to the no-maybe-results rule: the pinned Codon cannot compile the class-based
sum a maybe-type would need. Each is a named constant, compared by name at every use.

Integers and lists only, so the Codon census compiles it; the readers use nemik.tracker's parser
the way ratchetseries does.
"""

from nemik.ratchetpace import BEHIND, OK, verdict
from nemik.tracker import DICT, INT, LIST, REAL, Tree, parse_tree

NAME = "mikemol.commitments.open"
RATCHET = "commitments/open"
RATCHET_FAMILY = "mikemol.ratchet.value"  # the family of the landing clock
STALE_PERIODS = 4  # census periods a sample stays fresh
UNMEASURED = -1  # a landing with no usable census sample, or a corrupt count
NO_SAMPLE = -1  # latest_at: no sample at or before the time
NO_PERIOD = 0  # census_period: too few samples to have a gap
NO_DARK = -1  # judge: no UNMEASURED point in the series
UNKNOWN = "unknown"
LANDED = "landed"  # the `stage` label of a sample sent after its commit landed (mtools:W2171)
FEWEST_FOR_A_GAP = 2

Samples = list[tuple[int, int]]


def census_period(times: list[int]) -> int:
    """Read a series' census period as the median gap between its sample times.

    Args:
        times: The sample times in milliseconds, oldest first.

    Returns:
        The median gap, or NO_PERIOD for fewer than two samples.

    """
    if len(times) < FEWEST_FOR_A_GAP:
        return NO_PERIOD
    gaps = sorted(times[at + 1] - times[at] for at in range(len(times) - 1))
    return gaps[len(gaps) // 2]


def latest_at(samples: Samples, when: int) -> int:
    """Find the newest sample at or before a time.

    Args:
        samples: (time in milliseconds, count), oldest first.
        when: The time to look back from.

    Returns:
        The index of the newest sample at or before `when`, or NO_SAMPLE when none is.

    """
    low, high = 0, len(samples)
    while low < high:
        middle = (low + high) // 2
        if samples[middle][0] <= when:
            low = middle + 1
        else:
            high = middle
    return low - 1 if low > 0 else NO_SAMPLE


def at_landing(layers: list[Samples], when: int) -> int:
    """Total the open commitments of a repo at one landing.

    Args:
        layers: The repo's per-layer series, each (time in milliseconds, count) oldest first.
        when: The landing's time in milliseconds.

    Returns:
        The sum of each layer's newest sample at or before `when`, over the layers that had begun;
        UNMEASURED when any such layer's sample is corrupt or older than STALE_PERIODS of that
        layer's own census periods (a layer with one sample has no period, so only a sample at
        the landing's own instant is fresh), and when no layer has begun.

    """
    total = 0
    begun = 0
    for samples in layers:
        at = latest_at(samples, when)
        if at == NO_SAMPLE:
            continue
        count = samples[at][1]
        bound = STALE_PERIODS * census_period([time for time, _ in samples])
        if count == UNMEASURED or when - samples[at][0] > bound:
            return UNMEASURED
        total += count
        begun += 1
    return total if begun else UNMEASURED


def resample(layers: list[Samples], landings: list[int]) -> list[int]:
    """Put a repo's census series on its landing clock.

    Returns:
        One value per landing, oldest first: the open count then, or UNMEASURED.

    """
    return [at_landing(layers, when) for when in sorted(landings)]


def judge(points: list[int], window: int, prior: int) -> tuple[str, int, int]:
    """Judge the resampled series: ratchetpace's verdict, UNKNOWN where the census went dark.

    Args:
        points: resample's values, oldest first.
        window: How many landings one window spans.
        prior: The largest requirement stated before.

    Returns:
        (state, observed fall, required fall). `unknown` (with 0 and 0) when the series is empty or
        any of the last window + 1 points, the ones the observed fall spans, is UNMEASURED. Else
        ratchetpace.verdict over the measured run since the last UNMEASURED point, so a dark
        stretch long ago leaves a shorter history, never a made-up one.

    """
    if not points or UNMEASURED in points[-(window + 1) :]:
        return UNKNOWN, 0, 0
    last_dark = NO_DARK
    for at, value in enumerate(points):
        if value == UNMEASURED:
            last_dark = at
    state, fell, owed = verdict(points[last_dark + 1 :], window, prior)
    return (BEHIND if state == BEHIND else OK), fell, owed


def _number(tree: Tree, at: int) -> bool:
    """Say whether a value is a number.

    Returns:
        True for an integer or a real.

    """
    return tree.kinds[at] in {INT, REAL}


def _whole(tree: Tree, at: int) -> int:
    """Read a number as a whole number, a real truncated.

    Returns:
        The integer.

    """
    return tree.wholes[at] if tree.kinds[at] == INT else int(tree.reals[at])


def _lines(text: str) -> list[tuple[Tree, int, int, int]]:
    """Parse the export's series lines.

    Returns:
        (tree, metric handle, values handle, timestamps handle) per line that is a series.

    """
    out: list[tuple[Tree, int, int, int]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            tree = parse_tree(line)
        except ValueError:
            continue
        body = tree.root
        if tree.kinds[body] != DICT:
            continue
        metric = tree.get(body, "metric")
        values, stamps = tree.get(body, "values"), tree.get(body, "timestamps")
        if (
            tree.kinds[metric] == DICT
            and tree.kinds[values] == LIST
            and tree.kinds[stamps] == LIST
        ):
            out.append((tree, metric, values, stamps))
    return out


def _raw(tree: Tree, stamps: int, values: int) -> Samples:
    """Read one series' samples as written.

    Returns:
        (time in milliseconds, count), oldest first; a count may be negative here.

    """
    times, counts = tree.kids[stamps], tree.kids[values]
    found: Samples = []
    for place in range(min(len(times), len(counts))):
        if _number(tree, times[place]) and _number(tree, counts[place]):
            found.append((_whole(tree, times[place]), _whole(tree, counts[place])))
    return sorted(found)


def _samples(tree: Tree, stamps: int, values: int) -> Samples:
    """Read one series' samples, a corrupt (negative) count as UNMEASURED.

    Returns:
        (time in milliseconds, count or UNMEASURED), oldest first.

    """
    return [
        (when, count if count >= 0 else UNMEASURED)
        for when, count in _raw(tree, stamps, values)
    ]


def commitment_layers(text: str) -> dict[str, list[Samples]]:
    """Read the census family out of a store export, one list of layer series per repo.

    Args:
        text: The export's lines, one JSON series per line.

    Returns:
        repo -> its layers' series; a line of another family, or with no repo, is skipped.

    """
    out: dict[str, list[Samples]] = {}
    for tree, metric, values, stamps in _lines(text):
        repo = tree.string(metric, "repo")
        if tree.string(metric, "__name__") == NAME and repo:
            out.setdefault(repo, []).append(_samples(tree, stamps, values))
    return out


def corrupt(text: str) -> list[str]:
    """Name the census samples whose count is negative, for a reading note.

    Args:
        text: The export's lines, one JSON series per line.

    Returns:
        One "repo layer at <milliseconds>" per negative sample, in the export's order; each such
        point reads UNMEASURED, never zero.

    """
    out: list[str] = []
    for tree, metric, values, stamps in _lines(text):
        repo = tree.string(metric, "repo")
        if tree.string(metric, "__name__") == NAME and repo:
            layer = tree.string(metric, "layer")
            out.extend(
                f"{repo} {layer} at {when}"
                for when, count in _raw(tree, stamps, values)
                if count < 0
            )
    return out


def landing_times(text: str) -> dict[str, list[int]]:
    """Read each repo's landing clock: the times of its `stage=landed` ratchet samples.

    Args:
        text: The export's lines, one JSON series per line.

    Returns:
        repo -> the distinct landing times in milliseconds, oldest first; only series of the
        mikemol.ratchet.value family count, so another family that reuses the label cannot add
        landings.

    """
    seen: dict[str, set[int]] = {}
    for tree, metric, values, stamps in _lines(text):
        repo = tree.string(metric, "repo")
        landed = tree.string(metric, "stage") == LANDED
        if landed and tree.string(metric, "__name__") == RATCHET_FAMILY and repo:
            held = seen.setdefault(repo, set())
            for when, _ in _raw(tree, stamps, values):
                held.add(when)
    return {repo: sorted(times) for repo, times in seen.items()}


def commitment_points(text: str) -> dict[str, list[int]]:
    """Resample every repo's census onto its landing clock.

    Returns:
        repo -> resample's points; a repo with a census but no landing has none and is left out.

    """
    layers, landings = commitment_layers(text), landing_times(text)
    return {
        repo: resample(series, landings[repo])
        for repo, series in sorted(layers.items())
        if landings.get(repo)
    }
