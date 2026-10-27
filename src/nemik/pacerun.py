# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1030: one pace run: the store's ratchet series and the last file in, the new file out.

The host job gets either a range-query answer over mikemol.ratchet.value or the store's raw export
of it, one sample per gate run (ratchetseries, nemik:W996, W1032), and reads the pace file it wrote
last time (pacepublish.read_pace). Each series is judged by pacewrite against the requirement the
last file stated, which only rises, and the result is the file text pacepublish reads. A last file
that is missing or unreadable seeds nothing, except the floors the store itself remembers: the
required fall is published as nemik_ratchet_fall_required, and its highest sample per ratchet is a
prior no local file loss can take away (nemik:W1126).
"""

from nemik.pacepublish import Row, read_pace
from nemik.pacewrite import (
    contradictions,
    extras_of,
    pace_rows,
    pace_text,
    priors_of,
)
from nemik.ratchetpace import WINDOW
from nemik.ratchetseries import ended_series, export_series, series_of
from nemik.rebaselines import DECLARED, RESETS, reset_table, since

ANSWER_HEAD = '{"status"'
# the two metric names a required-fall export may hold, told apart by their __name__ label
REQUIRED_NAME = '"__name__":"nemik_ratchet_fall_required"'
VALUE_NAME = '"__name__":"mikemol.ratchet.value"'


def floors_of(export: str) -> dict[str, int]:
    """Read the highest required fall the store holds for each ratchet.

    Args:
        export: The store's raw export of nemik_ratchet_fall_required, one series per line.

    Returns:
        The largest sample under the key `repo` and `ratchet` joined by a newline, as priors_of
        keys them; empty when the export holds no series.

    """
    return {
        f"{repo}\n{ratchet}": max(values)
        for repo, ratchet, values in export_series(export)
        if values
    }


def retired_of(export: str) -> frozenset[str]:
    """Name the ratchets the store lists a tombstone for (nemik:W1040).

    mtools emits mikemol.ratchet.retired{repo, ratchet, reason} = 1 on every run while the tombstone
    stands; a ratchet's absence from the value series is only a retirement when one is written.

    Args:
        export: The store's raw export of mikemol.ratchet.retired, one series per line.

    Returns:
        The `repo` and `ratchet` keys, joined by a newline, whose newest sample is 1 or more; empty
        when the export holds no series, as before the emitter ran.

    """
    return frozenset(
        f"{repo}\n{ratchet}"
        for repo, ratchet, values in export_series(export)
        if values and values[-1] >= 1
    )


def resets_of(export: str) -> list[str]:
    """Name the ratchets whose required fall now stands below a level it once held.

    The requirement only rises, so a series whose last sample is under its highest has been reset
    (mypy 2 to 1 after the pace outage, nemik:W1126): the semantics luthen's alert over
    nemik_ratchet_fall_required carries (luthen-observability:W1685).

    Args:
        export: The store's raw export of nemik_ratchet_fall_required, one series per line.

    Returns:
        The `repo` and `ratchet` keys, joined by a newline, of the reset series; empty when every
        series only rose or held.

    """
    required = [line for line in export.splitlines() if REQUIRED_NAME in line]
    now = {
        f"{repo}\n{ratchet}": values[-1]
        for repo, ratchet, values in export_series(
            "\n".join(line for line in export.splitlines() if VALUE_NAME in line)
        )
        if values
    }
    return [
        f"{repo}\n{ratchet}"
        for repo, ratchet, values in export_series("\n".join(required))
        if values
        and values[-1] < max(values)
        and values[-1] < now.get(f"{repo}\n{ratchet}", values[-1] + 1)
    ]


def pace_document(answer: str, previous: str, stamp: str) -> str:
    """Judge every ratchet series of an answer and write the pace file, with no store floors.

    Returns:
        pace_document_floored's text with no floors.

    """
    return pace_document_floored(answer, previous, stamp, {})


def pace_document_floored(
    answer: str,
    previous: str,
    stamp: str,
    floors: dict[str, int],
    retired: frozenset[str] = frozenset(),
) -> str:
    """Judge every ratchet series of an answer and write the pace file.

    Args:
        answer: The store's range-query answer (a JSON object with a status), or its raw export
            (one series per line); the first form is told by its opening.
        previous: The pace file the last run wrote, empty when there is none.
        stamp: When this run reads the store, a UTC stamp.
        floors: The requirements the store remembers (floors_of); each only raises the prior.
        retired: The ratchets with a tombstone in the store (retired_of).

    Returns:
        The pace file's text, one row per ratchet series. A series of the export that ended while
        its repo's others went on reads unknown (nemik:W1039), never ok and never behind, unless
        the store lists its tombstone (nemik:W1040), when it leaves the file: a retired ratchet
        has no verdict to give, and one that is still written stays judged. A series
        with a declared re-baseline (nemik:W1046) is judged from the declared step on, so the
        step earns no paydown credit. A stated requirement that a declared reset names (nemik:W1165)
        is read as the declared new one, from the previous file and from the store's floor alike.
        Each row also states the ratchet's value and its horizon,
        the landings to zero at the pace it last fell (nemik:W1114). An answer that holds no
        series raises ValueError, so no empty file replaces a good one.

    """
    series, rows = _judged(answer, previous, floors, retired)
    return pace_text(rows, stamp, WINDOW, extras_of(series, WINDOW))


def pace_contradictions(
    answer: str,
    previous: str,
    floors: dict[str, int],
    retired: frozenset[str] = frozenset(),
) -> list[str]:
    """Name the rows of a pace run that read behind though their series fell what they owed.

    The self-check beside the pace file (nemik:W1155): an alert, never a gate. It judges the
    answer as pace_document_floored does and lets pacewrite.contradictions compare each verdict
    with an independent recomputation.

    Returns:
        One line per contradicting row; none when the verdicts agree with their series.

    """
    series, rows = _judged(answer, previous, floors, retired)
    return contradictions(series, WINDOW, rows)


def _judged(
    answer: str, previous: str, floors: dict[str, int], retired: frozenset[str]
) -> tuple[list[tuple[str, str, list[int]]], list[Row]]:
    """Judge every ratchet series of an answer.

    Returns:
        The series each row was judged on (from the declared re-baseline on) and the rows.

    Raises:
        ValueError: When the answer holds no series, so no empty file replaces a good one.

    """
    try:
        priors = reset_table(priors_of(read_pace(previous)[2]), RESETS)
    except ValueError:
        priors = {}
    for key, floor in reset_table(floors, RESETS).items():
        priors[key] = max(priors.get(key, 0), floor)
    is_answer = answer.lstrip().startswith(ANSWER_HEAD)
    read = series_of(answer) if is_answer else export_series(answer)
    ended = [] if is_answer else ended_series(answer)
    gone = {f"{repo}\n{ratchet}" for repo, ratchet in ended} & retired
    series = [
        (repo, ratchet, since(values, repo, ratchet, DECLARED))
        for repo, ratchet, values in read
        if f"{repo}\n{ratchet}" not in gone
    ]
    ended = [pair for pair in ended if f"{pair[0]}\n{pair[1]}" not in gone]
    if not series:
        message = "the answer holds no ratchet series"
        raise ValueError(message)
    return series, pace_rows(series, WINDOW, priors, ended)
