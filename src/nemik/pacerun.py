# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1030: one pace run: the store's ratchet series and the last file in, the new file out.

The host job gets either a range-query answer over mikemol.ratchet.value or the store's raw export
of it, one sample per gate run (ratchetseries, nemik:W996, W1032), and reads the pace file it wrote
last time (pacepublish.read_pace). Each series is judged by pacewrite against the requirement the
last file stated, which only rises, and the result is the file text pacepublish reads. A last file
that is missing or unreadable seeds nothing: every requirement then starts from the series alone.
"""

from nemik.pacepublish import read_pace
from nemik.pacewrite import pace_rows, pace_text, priors_of
from nemik.ratchetpace import WINDOW
from nemik.ratchetseries import export_series, series_of

ANSWER_HEAD = '{"status"'


def pace_document(answer: str, previous: str, stamp: str) -> str:
    """Judge every ratchet series of an answer and write the pace file.

    Args:
        answer: The store's range-query answer (a JSON object with a status), or its raw export
            (one series per line); the first form is told by its opening.
        previous: The pace file the last run wrote, empty when there is none.
        stamp: When this run reads the store, a UTC stamp.

    Returns:
        The pace file's text, one row per ratchet series.

    Raises:
        ValueError: When the answer holds no series, so no empty file replaces a good one.

    """
    try:
        priors = priors_of(read_pace(previous)[2])
    except ValueError:
        priors = {}
    series = (
        series_of(answer)
        if answer.lstrip().startswith(ANSWER_HEAD)
        else export_series(answer)
    )
    if not series:
        message = "the answer holds no ratchet series"
        raise ValueError(message)
    return pace_text(pace_rows(series, WINDOW, priors), stamp, WINDOW)
