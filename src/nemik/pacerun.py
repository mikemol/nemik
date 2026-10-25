# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1030: one pace run: the store's ratchet series and the last file in, the new file out.

The host job gets a range-query answer over mikemol.ratchet.value (ratchetseries, nemik:W996) and
reads the pace file it wrote last time (pacepublish.read_pace). Each series is judged by pacewrite
against the requirement the last file stated, which only rises, and the result is the file text
pacepublish reads. A last file that is missing or unreadable seeds nothing: every requirement then
starts from the series alone.
"""

from nemik.pacepublish import read_pace
from nemik.pacewrite import pace_rows, pace_text, priors_of
from nemik.ratchetpace import WINDOW
from nemik.ratchetseries import series_of


def pace_document(answer: str, previous: str, stamp: str) -> str:
    """Judge every ratchet series of an answer and write the pace file.

    Args:
        answer: The store's JSON answer to a range query over mikemol.ratchet.value.
        previous: The pace file the last run wrote, empty when there is none.
        stamp: When this run reads the store, a UTC stamp.

    Returns:
        The pace file's text, one row per ratchet series.

    """
    try:
        priors = priors_of(read_pace(previous)[2])
    except ValueError:
        priors = {}
    return pace_text(pace_rows(series_of(answer), WINDOW, priors), stamp, WINDOW)
