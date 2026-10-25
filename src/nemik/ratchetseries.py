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
