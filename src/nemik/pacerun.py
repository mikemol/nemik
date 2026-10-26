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

from nemik.pacepublish import read_pace
from nemik.pacewrite import extras_of, pace_rows, pace_text, priors_of
from nemik.ratchetpace import WINDOW
from nemik.ratchetseries import ended_series, export_series, series_of
from nemik.rebaselines import DECLARED, since

ANSWER_HEAD = '{"status"'


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


def pace_document(answer: str, previous: str, stamp: str) -> str:
    """Judge every ratchet series of an answer and write the pace file, with no store floors.

    Returns:
        pace_document_floored's text with no floors.

    """
    return pace_document_floored(answer, previous, stamp, {})


def pace_document_floored(
    answer: str, previous: str, stamp: str, floors: dict[str, int]
) -> str:
    """Judge every ratchet series of an answer and write the pace file.

    Args:
        answer: The store's range-query answer (a JSON object with a status), or its raw export
            (one series per line); the first form is told by its opening.
        previous: The pace file the last run wrote, empty when there is none.
        stamp: When this run reads the store, a UTC stamp.
        floors: The requirements the store remembers (floors_of); each only raises the prior.

    Returns:
        The pace file's text, one row per ratchet series. A series of the export that ended while
        its repo's others went on reads unknown (nemik:W1039), never ok and never behind. A series
        with a declared re-baseline (nemik:W1046) is judged from the declared step on, so the
        step earns no paydown credit. Each row also states the ratchet's value and its horizon,
        the landings to zero at the pace it last fell (nemik:W1114).

    Raises:
        ValueError: When the answer holds no series, so no empty file replaces a good one.

    """
    try:
        priors = priors_of(read_pace(previous)[2])
    except ValueError:
        priors = {}
    for key, floor in floors.items():
        priors[key] = max(priors.get(key, 0), floor)
    is_answer = answer.lstrip().startswith(ANSWER_HEAD)
    read = series_of(answer) if is_answer else export_series(answer)
    series = [
        (repo, ratchet, since(values, repo, ratchet, DECLARED))
        for repo, ratchet, values in read
    ]
    ended = [] if is_answer else ended_series(answer)
    if not series:
        message = "the answer holds no ratchet series"
        raise ValueError(message)
    rows = pace_rows(series, WINDOW, priors, ended)
    return pace_text(rows, stamp, WINDOW, extras_of(series, WINDOW))
