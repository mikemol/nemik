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

from nemik.tracker import DICT, INT, LIST, REAL, STR, Tree, parse_tree

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
    tree = parse_tree(answer)
    body = tree.root
    if tree.kinds[body] != DICT or tree.string(body, "status") != "success":
        message = "the answer is not a successful query"
        raise TypeError(message)
    result = tree.get(tree.get(body, "data"), "result")
    if tree.kinds[result] != LIST:
        message = "the answer has no result list"
        raise TypeError(message)
    out: list[tuple[str, str, list[int]]] = []
    for entry in tree.kids[result]:
        if tree.kinds[entry] != DICT:
            continue
        metric, samples = tree.get(entry, "metric"), tree.get(entry, "values")
        if tree.kinds[metric] != DICT or tree.kinds[samples] != LIST:
            continue
        repo, ratchet = tree.string(metric, "repo"), tree.string(metric, "ratchet")
        if repo and ratchet and repo != PHANTOM:
            out.append((repo, ratchet, _counts(tree, samples)))
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


def _hold(
    held: dict[int, tuple[int, int]],
    tree: Tree,
    stamps: int,
    values: int,
    declared: int,
) -> None:
    """Add a series' samples to its ratchet's, the declared sample winning a shared instant.

    Args:
        held: The ratchet's samples so far, by time: (0 declared or 1 guessed, the count).
        tree: The parsed line.
        stamps: The handle of the series' sample times, a list of milliseconds.
        values: The handle of its sample values, a list.
        declared: 0 for a guessed=false series, 1 for any other.

    """
    times, counts = tree.kids[stamps], tree.kids[values]
    for place in range(min(len(times), len(counts))):
        if _number(tree, times[place]) and _number(tree, counts[place]):
            mine = (declared, max(0, _whole(tree, counts[place])))
            when = _whole(tree, times[place])
            if when not in held or mine < held[when]:
                held[when] = mine


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
            tree.kinds[metric] != DICT
            or tree.kinds[values] != LIST
            or tree.kinds[stamps] != LIST
        ):
            continue
        repo, ratchet = tree.string(metric, "repo"), tree.string(metric, "ratchet")
        if repo and ratchet and repo != PHANTOM:
            declared = 0 if tree.string(metric, "guessed") == "false" else 1
            held = merged.setdefault((repo, ratchet), {})
            _hold(held, tree, stamps, values, declared)
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


def _counts(tree: Tree, samples: int) -> list[int]:
    """Turn [seconds, "value"] pairs into whole counts, oldest first.

    Returns:
        The values as integers floored at zero; a pair that is not a time and a number is skipped.

    """
    pairs: list[tuple[int, int]] = []
    for pair in tree.kids[samples]:
        if tree.kinds[pair] == LIST and len(tree.kids[pair]) == PAIR:
            at, value = tree.kids[pair]
            if _number(tree, at) and tree.kinds[value] == STR:
                text = tree.texts[value]
                pairs.append((_whole(tree, at), max(0, int(float(text)))))
    return [count for _, count in sorted(pairs)]
