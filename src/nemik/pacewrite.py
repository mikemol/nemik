# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W997: the pace file written from the ratchet series, one verdict row per ratchet.

ratchetseries (nemik:W996) reads luthen's range answer into one value list per ratchet; ratchetpace
(nemik:W987) judges a list; pacepublish (nemik:W990) reads the file this writes. The first line
carries `"as_of"` and `"window"`, then one flat object per line: repo, ratchet, state, observed and
required, the numbers as quoted text. The requirement only rises: the previous file's requirement
for the same ratchet is passed back as the prior, and the larger one is written.
"""

from nemik.pacepublish import Row
from nemik.ratchetpace import verdict


def priors_of(rows: list[Row]) -> dict[str, int]:
    """Key the previous file's requirements by repo and ratchet.

    Returns:
        The required fall of each row, under the key `repo` and `ratchet` joined by a newline.

    """
    return {f"{repo}\n{ratchet}": owed for repo, ratchet, _, _, owed in rows}


def pace_rows(
    series: list[tuple[str, str, list[int]]], window: int, priors: dict[str, int]
) -> list[Row]:
    """Judge each series.

    Args:
        series: (repo, ratchet, values oldest first), as ratchetseries reads them.
        window: How many landed commits one window spans.
        priors: The requirements the previous file stated, from priors_of.

    Returns:
        One (repo, ratchet, state, observed, required) row per series, in the order given.

    """
    rows: list[Row] = []
    for repo, ratchet, values in series:
        state, seen, owed = verdict(values, window, priors.get(f"{repo}\n{ratchet}", 0))
        rows.append((repo, ratchet, state, seen, owed))
    return rows


def pace_text(rows: list[Row], as_of: str, window: int) -> str:
    """Write the pace file.

    Args:
        rows: The verdict rows.
        as_of: When they were computed, a UTC stamp.
        window: The window in landed commits.

    Returns:
        The file's text: the head line, then one row per line.

    """
    lines = [f'{{"as_of": "{as_of}", "window": "{window}"}}']
    for repo, ratchet, state, seen, owed in rows:
        lines.append(
            f'{{"repo": "{repo}", "ratchet": "{ratchet}", "state": "{state}", '
            f'"observed": "{seen}", "required": "{owed}"}}'
        )
    return "\n".join(lines) + "\n"
