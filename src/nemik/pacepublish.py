# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W990: the per-ratchet pace rows nemik publishes, read from the file the pace run writes.

ratchetpace (nemik:W987) judges a ratchet behind or ok; this module is the publishing side. The
pace file holds a first line carrying `"as_of"` and `"window"`, then one flat object per line:
{"repo", "ratchet", "state", "observed", "required"}, the ratchet named by its repo-relative path
(mtools-ad, 2026-10-24) and the numbers as quoted text, the way landings.json writes its rows. The
gauges a commit gate and luthen's alert read are `nemik_ratchet_behind{repo,ratchet}` with the
state as the 0/1 value (1 is behind), beside `nemik_ratchet_fall_observed` and
`nemik_ratchet_fall_required`. The lines are read with hostroot's flat-JSON reader.
"""

from nemik.hostroot import fields

AS_OF_KEY = '"as_of": "'
WINDOW_KEY = '"window": "'
BEHIND = "behind"
OK = "ok"
PACE_FILE = "ratchet-pace.json"
GAUGE_BEHIND = "nemik_ratchet_behind"
GAUGE_OBSERVED = "nemik_ratchet_fall_observed"
GAUGE_REQUIRED = "nemik_ratchet_fall_required"

Row = tuple[str, str, str, int, int]


def _after(head: str, key: str) -> str:
    """Read the quoted value that follows a key on the first line.

    Returns:
        The text between the key's opening quote and its closing one, empty when absent.

    """
    at = head.find(key)
    if at < 0:
        return ""
    start = at + len(key)
    return head[start : head.find('"', start)]


def _first(body: dict[str, list[str]], key: str) -> str:
    """Read the single string a key holds.

    Returns:
        The key's first item.

    Raises:
        ValueError: When the key is absent or holds no item.

    """
    items = body.get(key, [])
    if len(items) == 0:
        message = f"no {key}"
        raise ValueError(message)
    return items[0]


def read_pace(text: str) -> tuple[str, int, list[Row]]:
    """Read the file the pace run writes.

    Args:
        text: The file's text.

    Returns:
        (when it was computed, the window in landed commits, the rows in the order written).

    Raises:
        ValueError: When the first line carries no as_of, or a row line misses a key or holds a
            state other than behind or ok.

    """
    lines = text.splitlines()
    head = lines[0] if lines else ""
    as_of = _after(head, AS_OF_KEY)
    if not as_of:
        message = "no as_of on the first line"
        raise ValueError(message)
    window = int(_after(head, WINDOW_KEY) or "0")
    rows: list[Row] = []
    for line in lines[1:]:
        body = line.strip().rstrip(",")
        if body.startswith("{"):
            got = fields(body)
            state = _first(got, "state")
            if state not in {BEHIND, OK}:
                message = f"state {state} is neither behind nor ok"
                raise ValueError(message)
            repo, ratchet = _first(got, "repo"), _first(got, "ratchet")
            seen, owed = int(_first(got, "observed")), int(_first(got, "required"))
            rows.append((repo, ratchet, state, seen, owed))
    return as_of, window, rows


def behind_ratchets(rows: list[Row], repo: str) -> list[str]:
    """Name the ratchets a repo is behind on.

    Returns:
        The ratchet paths of the repo's rows whose state is behind, in the order written.

    """
    return [
        ratchet
        for name, ratchet, state, _, _ in rows
        if name == repo and state == BEHIND
    ]


def metric_lines(rows: list[Row]) -> list[str]:
    """Write the gauges for the rows, Prometheus text.

    Returns:
        A TYPE line and one sample per row for each gauge; the state is 1 when behind, else 0.

    """
    out = [f"# TYPE {GAUGE_BEHIND} gauge"]
    for repo, ratchet, state, _, _ in rows:
        value = 1 if state == BEHIND else 0
        out.append(f'{GAUGE_BEHIND}{{repo="{repo}",ratchet="{ratchet}"}} {value}')
    out.append(f"# TYPE {GAUGE_OBSERVED} gauge")
    for repo, ratchet, _, seen, _ in rows:
        out.append(f'{GAUGE_OBSERVED}{{repo="{repo}",ratchet="{ratchet}"}} {seen}')
    out.append(f"# TYPE {GAUGE_REQUIRED} gauge")
    for repo, ratchet, _, _, owed in rows:
        out.append(f'{GAUGE_REQUIRED}{{repo="{repo}",ratchet="{ratchet}"}} {owed}')
    return out
