# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W997: the pace file written from the ratchet series, one verdict row per ratchet.

ratchetseries (nemik:W996) reads luthen's range answer into one value list per ratchet; ratchetpace
(nemik:W987) judges a list; pacepublish (nemik:W990) reads the file this writes. The first line
carries `"as_of"` and `"window"`, then one flat object per line: repo, ratchet, state, observed and
required, the numbers as quoted text. The requirement only rises: the previous file's requirement
for the same ratchet is passed back as the prior, and the larger one is written.
"""

from nemik.pacepublish import UNKNOWN, Row
from nemik.ratchetpace import BEHIND, horizon, verdict


def extras_of(
    series: list[tuple[str, str, list[int]]], window: int
) -> dict[str, tuple[int, int]]:
    """State each ratchet's value and landings-to-zero (nemik:W1114).

    Args:
        series: (repo, ratchet, values oldest first), as ratchetseries reads them.
        window: How many landed commits one window spans.

    Returns:
        (value now, horizon) under the key `repo` and `ratchet` joined by a newline; the horizon is
        -1 when nothing fell over the window.

    """
    return {
        f"{repo}\n{ratchet}": (values[-1] if values else 0, horizon(values, window))
        for repo, ratchet, values in series
    }


def priors_of(rows: list[Row]) -> dict[str, int]:
    """Key the previous file's requirements by repo and ratchet.

    Returns:
        The required fall of each row, under the key `repo` and `ratchet` joined by a newline.

    """
    return {f"{repo}\n{ratchet}": owed for repo, ratchet, _, _, owed in rows}


def pace_rows(
    series: list[tuple[str, str, list[int]]],
    window: int,
    priors: dict[str, int],
    ended: list[tuple[str, str]],
) -> list[Row]:
    """Judge each series.

    Args:
        series: (repo, ratchet, values oldest first), as ratchetseries reads them.
        window: How many landed commits one window spans.
        priors: The requirements the previous file stated, from priors_of.
        ended: The (repo, ratchet) pairs whose series ended while their repo's others went on.

    Returns:
        One (repo, ratchet, state, observed, required) row per series, in the order given. An ended
        series reads unknown, observed 0 and the requirement it last stated: absence is a reading
        about the instrument, and only a written tombstone retires a ratchet (operator, host
        695f3e0a line 96701), so it is neither ok nor behind.

    """
    gone = set(ended)
    rows: list[Row] = []
    for repo, ratchet, values in series:
        prior = priors.get(f"{repo}\n{ratchet}", 0)
        if (repo, ratchet) in gone:
            rows.append((repo, ratchet, UNKNOWN, 0, prior))
            continue
        state, seen, owed = verdict(values, window, prior)
        rows.append((repo, ratchet, state, seen, owed))
    return rows


def contradictions(
    series: list[tuple[str, str, list[int]]], window: int, rows: list[Row]
) -> list[str]:
    """Name the rows that read behind while their own series fell what they owed (nemik:W1155).

    A self-check, an alert and never a gate: it recomputes the fall over the last `window`
    landings of the very series a row was judged on, by its own loop and not by window_fall, and
    says so when the row reads behind though that fall is at least the requirement. A row can only
    do that if the verdict and the series disagree, which is how linux-sources' letter-quotes read
    behind with observed 0 while it fell 18 to 2 (a short history, W1155).

    Args:
        series: (repo, ratchet, values oldest first), the series each row was judged on.
        window: How many landed commits one window spans.
        rows: The verdict rows, in the order of `series`.

    Returns:
        One line per contradicting row; none when every behind row really did fall short.

    """
    found: list[str] = []
    for at, (repo, ratchet, values) in enumerate(series):
        owed = rows[at][4]
        if rows[at][2] != BEHIND or owed <= 0:
            continue
        span = values[max(0, len(values) - 1 - window) :]
        fell = span[0] - span[-1] if span else 0
        if fell >= owed:
            found.append(
                f"{repo} {ratchet} reads behind (owes {owed}) but fell {fell} over its "
                f"last {len(span) - 1} landings"
            )
    return found


def pace_text(
    rows: list[Row], as_of: str, window: int, extras: dict[str, tuple[int, int]]
) -> str:
    """Write the pace file.

    Args:
        rows: The verdict rows.
        as_of: When they were computed, a UTC stamp.
        window: The window in landed commits.
        extras: Each ratchet's value and horizon, from extras_of; a row without one states neither.

    Returns:
        The file's text: the head line, then one row per line.

    """
    lines = [f'{{"as_of": "{as_of}", "window": "{window}"}}']
    for repo, ratchet, state, seen, owed in rows:
        more = ""
        if f"{repo}\n{ratchet}" in extras:
            value, reach = extras[f"{repo}\n{ratchet}"]
            more = f', "value": "{value}", "horizon": "{reach}"'
        lines.append(
            f'{{"repo": "{repo}", "ratchet": "{ratchet}", "state": "{state}", '
            f'"observed": "{seen}", "required": "{owed}"{more}}}'
        )
    return "\n".join(lines) + "\n"
