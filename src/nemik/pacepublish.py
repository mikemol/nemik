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
# a series ended with no tombstone: neither ok nor behind (nemik:W1039)
UNKNOWN = "unknown"
STATES = (BEHIND, OK, UNKNOWN)
PACE_FILE = "ratchet-pace.json"
GAUGE_UNKNOWN = "nemik_ratchet_unknown"
GAUGE_AS_OF = "nemik_ratchet_pace_as_of"
STAMP_LENGTH = 20  # YYYY-MM-DDTHH:MM:SSZ
MARCH = 3
DAYS_PER_ERA = 146097  # days in 400 Gregorian years
DAYS_TO_1970 = 719468  # days from 0000-03-01 to 1970-01-01
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
    # a stamp that is not UTC time is refused here, not at publication
    epoch_seconds(as_of)
    window = int(_after(head, WINDOW_KEY) or "0")
    rows: list[Row] = []
    for line in lines[1:]:
        body = line.strip().rstrip(",")
        if body.startswith("{"):
            got = fields(body)
            state = _first(got, "state")
            if state not in STATES:
                message = f"state {state} is none of behind, ok or unknown"
                raise ValueError(message)
            repo, ratchet = _first(got, "repo"), _first(got, "ratchet")
            seen, owed = int(_first(got, "observed")), int(_first(got, "required"))
            rows.append((repo, ratchet, state, seen, owed))
    return as_of, window, rows


def epoch_seconds(stamp: str) -> int:
    """Convert an ISO stamp like 2026-10-24T19:00:00Z to unix seconds, by integer arithmetic.

    Args:
        stamp: A UTC stamp, YYYY-MM-DDTHH:MM:SSZ.

    Returns:
        Seconds since 1970-01-01T00:00:00Z.

    Raises:
        ValueError: When the stamp is not that shape.

    """
    if len(stamp) < STAMP_LENGTH or stamp[4] != "-" or stamp[10] != "T":
        message = f"not a UTC stamp: {stamp}"
        raise ValueError(message)
    year, month, day = int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10])
    hour, minute, second = int(stamp[11:13]), int(stamp[14:16]), int(stamp[17:19])
    shifted = year - 1 if month < MARCH else year
    era = shifted // 400
    in_era = shifted - era * 400
    from_march = (month + 9) % 12
    in_year = (153 * from_march + 2) // 5 + day - 1
    in_era_days = in_era * 365 + in_era // 4 - in_era // 100 + in_year
    days = era * DAYS_PER_ERA + in_era_days - DAYS_TO_1970
    return days * 86400 + hour * 3600 + minute * 60 + second


def as_of_lines(stamp: str) -> list[str]:
    """Write the gauge that dates the pace file, Prometheus text.

    Returns:
        A TYPE line and one sample whose value is the stamp in unix seconds, so an alert reads a
        stale verdict as age and not as a missing sample.

    """
    return [f"# TYPE {GAUGE_AS_OF} gauge", f"{GAUGE_AS_OF} {epoch_seconds(stamp)}"]


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


def metric_lines(rows: list[Row], as_of: str) -> list[str]:
    """Write the gauges for the rows and the file's age stamp, Prometheus text.

    Returns:
        A TYPE line and one sample per row for each gauge, the state 1 when behind and else 0, then
        the gauge that dates the file.

    """
    out = [f"# TYPE {GAUGE_BEHIND} gauge"]
    for repo, ratchet, state, _, _ in rows:
        value = 1 if state == BEHIND else 0
        out.append(f'{GAUGE_BEHIND}{{repo="{repo}",ratchet="{ratchet}"}} {value}')
    out.append(f"# TYPE {GAUGE_UNKNOWN} gauge")
    for repo, ratchet, state, _, _ in rows:
        value = 1 if state == UNKNOWN else 0
        out.append(f'{GAUGE_UNKNOWN}{{repo="{repo}",ratchet="{ratchet}"}} {value}')
    out.append(f"# TYPE {GAUGE_OBSERVED} gauge")
    for repo, ratchet, _, seen, _ in rows:
        out.append(f'{GAUGE_OBSERVED}{{repo="{repo}",ratchet="{ratchet}"}} {seen}')
    out.append(f"# TYPE {GAUGE_REQUIRED} gauge")
    for repo, ratchet, _, _, owed in rows:
        out.append(f'{GAUGE_REQUIRED}{{repo="{repo}",ratchet="{ratchet}"}} {owed}')
    return out + as_of_lines(as_of)
