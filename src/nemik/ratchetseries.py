# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W996: the ratchet value series of luthen's metric store, read into ordered value lists.

mtools' gate sends one `mikemol.ratchet.value{repo, ratchet, kind}` gauge per ratchet file per gate
run (mtools:W1909), the value being the file's entry count. A range query answers with a matrix: one
series per label set, its samples as [unix seconds, "value"] pairs. ratchetpace (nemik:W987) takes a
ratchet's values oldest first, one per landing, so this reads an answer into exactly that.

The phantom repo `tree` is left out: before mtools:W1923 the label was read from the snapshot
directory, and about forty-five such series stay in the store until they age out.
"""

from nemik.tracker import Json, parse

PHANTOM = "tree"
PAIR = 2  # a sample is [unix seconds, "value"]
END_SLACK_MS = 60_000  # a repo's series from one gate run end within this of each other


def series_of(answer: str) -> list[tuple[str, str, list[int]]]:
    """Read a range-query answer into one value list per repo and ratchet.

    Args:
        answer: The store's JSON answer to a range query over mikemol.ratchet.value.

    Returns:
        (repo, ratchet, values oldest first) for each series, sorted by repo then ratchet; the
        values are whole entry counts, never below zero. Series of the phantom repo are left out.

    Raises:
        TypeError: When the answer is not a successful matrix of series.

    """
    body = parse(answer)
    if not isinstance(body, dict) or body.get("status") != "success":
        message = "the answer is not a successful query"
        raise TypeError(message)
    data = body.get("data")
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, list):
        message = "the answer has no result list"
        raise TypeError(message)
    out: list[tuple[str, str, list[int]]] = []
    for entry in result:
        if not isinstance(entry, dict):
            continue
        metric = entry.get("metric")
        samples = entry.get("values")
        if not isinstance(metric, dict) or not isinstance(samples, list):
            continue
        repo, ratchet = str(metric.get("repo", "")), str(metric.get("ratchet", ""))
        if repo and ratchet and repo != PHANTOM:
            out.append((repo, ratchet, _counts(samples)))
    return sorted(out, key=_by_name)


def export_series(text: str) -> list[tuple[str, str, list[int]]]:
    """Read the store's raw export into one value list per repo and ratchet (nemik:W1032).

    A range query answers on a clock, one point per step, so a quiet hour repeats the last value and
    a busy one drops landings; the export (`/api/v1/export`) holds the samples as written, one per
    gate run, which is the unit the pace counts. One JSON object per line:
    {"metric": {...}, "values": [...], "timestamps": [...]}.

    Args:
        text: The export's lines.

    Returns:
        (repo, ratchet, values oldest first) as series_of gives them, the phantom repo left out; a
        line that is not a series is skipped. A series that has ended is kept: ending is a reading
        about the instrument, not a verdict, and ended_series names those.

    """
    rows, _ = _export_rows(text)
    return sorted(
        [(repo, ratchet, counts) for repo, ratchet, counts, _ in rows], key=_by_name
    )


def ended_series(text: str) -> list[tuple[str, str]]:
    """Name the series that ended while their repo's other series went on (nemik:W1039).

    A retired ratchet, a gate that did not run and a broken emitter all look the same from here,
    so this infers nothing about which: the operator's ruling (host 695f3e0a line 96701) is that
    only a written tombstone drops a ratchet, and a silent one is unknown.

    Args:
        text: The export's lines.

    Returns:
        (repo, ratchet) for each series whose last sample is more than END_SLACK_MS before its
        repo's newest sample, sorted.

    """
    rows, newest = _export_rows(text)
    return sorted(
        (repo, ratchet)
        for repo, ratchet, _, end in rows
        if end < newest[repo] - END_SLACK_MS
    )


def _hold(
    held: dict[int, tuple[int, int]],
    stamps: list[Json],
    values: list[Json],
    declared: int,
) -> None:
    """Add a series' samples to its ratchet's, the declared sample winning a shared instant.

    Args:
        held: The ratchet's samples so far, by time: (0 declared or 1 guessed, the count).
        stamps: The series' sample times, milliseconds.
        values: Its sample values.
        declared: 0 for a guessed=false series, 1 for any other.

    """
    for at, value in zip(stamps, values, strict=False):
        if isinstance(at, int | float) and isinstance(value, int | float):
            mine = (declared, max(0, int(value)))
            if int(at) not in held or mine < held[int(at)]:
                held[int(at)] = mine


def _export_rows(
    text: str,
) -> tuple[list[tuple[str, str, list[int], int]], dict[str, int]]:
    """Read the export's series with the time of each one's last sample.

    Returns:
        (repo, ratchet, values oldest first, last sample time) per series, and each repo's newest
        sample time.

    """
    # nemik:W1038: a ratchet can have two series, one per `guessed` label (mtools:W1958), the older
    # guessed=true and the newer guessed=false. They are one ratchet: merged by sample time, the
    # declared (guessed=false) sample winning where both stamped the same instant. Kept apart they
    # read as a series that ended, and every row went unknown.
    merged: dict[tuple[str, str], dict[int, tuple[int, int]]] = {}
    for line in text.splitlines():
        try:
            body = parse(line) if line.strip() else None
        except ValueError:
            continue
        if not isinstance(body, dict):
            continue
        metric, values, stamps = (
            body.get("metric"),
            body.get("values"),
            body.get("timestamps"),
        )
        if not isinstance(metric, dict) or not isinstance(values, list):
            continue
        if not isinstance(stamps, list):
            continue
        repo, ratchet = str(metric.get("repo", "")), str(metric.get("ratchet", ""))
        if repo and ratchet and repo != PHANTOM:
            declared = 0 if str(metric.get("guessed", "")) == "false" else 1
            _hold(merged.setdefault((repo, ratchet), {}), stamps, values, declared)
    out: list[tuple[str, str, list[int], int]] = []
    newest: dict[str, int] = {}
    for (repo, ratchet), held in merged.items():
        ordered = sorted(held.items())
        end = ordered[-1][0] if ordered else 0
        out.append((repo, ratchet, [count for _, (_, count) in ordered], end))
        newest[repo] = max(newest.get(repo, 0), end)
    return out, newest


def _by_name(row: tuple[str, str, list[int]]) -> tuple[str, str]:
    """Order series by repo, then ratchet.

    Returns:
        The sort key.

    """
    return row[0], row[1]


def _counts(samples: list[Json]) -> list[int]:
    """Turn [seconds, "value"] pairs into whole counts, oldest first.

    Returns:
        The values as integers floored at zero; a pair that is not a time and a number is skipped.

    """
    pairs: list[tuple[int, int]] = []
    for pair in samples:
        if isinstance(pair, list) and len(pair) == PAIR:
            at, value = pair
            if isinstance(at, int | float) and isinstance(value, str):
                pairs.append((int(at), max(0, int(float(value)))))
    return [count for _, count in sorted(pairs)]
