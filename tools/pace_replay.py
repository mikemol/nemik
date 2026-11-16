# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""pace_replay: judge a ratchet's window under the current and a proposed rule (nemik:W2020).

Read-only. It walks every landing on main, oldest first, and for each one asks what the pace would
say about a ratchet: ok when the fall over the last ten landings is at least the required fall,
behind otherwise. The CURRENT rule takes the last ten landings of any kind. The PROPOSED rule takes
the last ten landings whose diff touched a file the ratchet measures (here: a python file under one
of its prefixes, or the baseline itself). It prints every landing where the two verdicts differ, and
then scores both rules against what happened next: a landing was STALLED when the value did not fall
below its value in the next ten measured landings. A verdict ok on a stalled landing is a false ok;
a verdict behind on a landing that fell soon is a false behind. Landings with fewer than ten
measured landings after them are left out of the score.
"""

import json
import sys
from pathlib import Path

from mikemol.procrun.proc import capture

WINDOW = 10
REQUIRED_FALL = 2
BASELINE = "codon-baseline.json"
MEASURED_PREFIX = "src/nemik/"
LOG_ARGS = ["log", "--reverse", "--format=@%h %ct", "--name-only", "main"]
SHOWN = 40
FIT_PERCENT = 70


def _table(value: object) -> dict[str, object]:
    """Read a parsed JSON value as an object, or an empty one when it is anything else.

    Returns:
        The object's entries, keyed by string.

    """
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _document(text: str) -> dict[str, object]:
    """Parse a baseline document.

    Returns:
        The top-level object, or an empty one when the text is not JSON or not an object.

    """
    try:
        parsed: object = json.loads(text)
    except ValueError:
        return {}
    return _table(parsed)


def entries(text: str) -> int:
    """Count the entries of a codon baseline document: one per module and compile mode.

    Returns:
        The number of string entries, or 0 when the text is not a baseline object.

    """
    return sum(len(_table(row)) for row in _document(text).values())


Spec = tuple[str, tuple[str, ...]]
CODON: Spec = (BASELINE, (MEASURED_PREFIX,))
LINT_PREFIXES = ("src/", "tests/", "tools/", "checks/")
RUFF: Spec = ("ruff-baseline.json", LINT_PREFIXES)
MYPY: Spec = ("mypy-baseline.json", LINT_PREFIXES)


def measured(files: list[str], spec: Spec = CODON) -> bool:
    """Say whether a landing's diff touched a file the ratchet measures.

    Args:
        files: The files the landing touched.
        spec: The ratchet's baseline file and the path prefixes of the python it measures.

    Returns:
        True when a file is the baseline or a python file under one of the prefixes.

    """
    baseline, prefixes = spec
    return any(
        name == baseline or (name.startswith(prefixes) and name.endswith(".py"))
        for name in files
    )


def pairs(text: str) -> int:
    """Count the (file, rule) pairs of a ruff or mypy baseline: {file: {rule: count}}.

    Returns:
        The number of rule entries, or 0 when the text is not a baseline object.

    """
    return sum(len(_table(row)) for row in _document(text).values())


def counts(text: str) -> int:
    """Sum the counts of a ruff or mypy baseline document: {file: {rule: count}}.

    Returns:
        The total of the integer counts, or 0 when the text is not a baseline object.

    """
    return sum(
        value
        for row in _document(text).values()
        for value in _table(row).values()
        if isinstance(value, int)
    )


def fall(values: list[int], window: int = WINDOW) -> int:
    """Give the fall over the last `window` values: the value before the window minus the newest.

    Returns:
        The fall (negative when the value rose); 0 when there are too few values.

    """
    if len(values) <= window:
        return 0
    return values[-window - 1] - values[-1]


def verdict(values: list[int]) -> str:
    """Judge a series of values: ok when the window fell by the required amount.

    Returns:
        `ok` or `behind`.

    """
    return "ok" if fall(values) >= REQUIRED_FALL else "behind"


def replay(
    landings: list[tuple[str, list[str], int]],
    spec: Spec = CODON,
) -> list[tuple[str, str, str]]:
    """Walk the landings oldest first and return those where the two rules disagree.

    Args:
        landings: (sha, files touched, ratchet value after the landing), oldest first.
        spec: The ratchet's baseline file and measured prefixes.

    Returns:
        (sha, current verdict, proposed verdict) for each landing where they differ.

    """
    every: list[int] = []
    counted: list[int] = []
    differing: list[tuple[str, str, str]] = []
    for sha, files, value in landings:
        every.append(value)
        if measured(files, spec):
            counted.append(value)
        current, proposed = verdict(every), verdict(counted)
        if current != proposed:
            differing.append((sha, current, proposed))
    return differing


def stalled(
    landings: list[tuple[str, list[str], int]],
    at: int,
    spec: Spec = CODON,
) -> bool | None:
    """Say whether the value stayed at or above landing `at`'s value for ten measured landings.

    Returns:
        True when no fall followed, False when one did, None when fewer than ten measured
        landings follow it.

    """
    here = landings[at][2]
    later = [
        value for _sha, files, value in landings[at + 1 :] if measured(files, spec)
    ]
    if len(later) < WINDOW:
        return None
    return min(later[:WINDOW]) >= here


def held_start(count: int, fit_percent: int = FIT_PERCENT) -> int:
    """Give the index where the held-out part of `count` landings begins (R462).

    Returns:
        The first held-out index: the landings before it are the fit part, in time order.

    """
    return count * fit_percent // 100


def fit_end(held: int, embargo: int = WINDOW) -> int:
    """Give the index where fitting must stop so no fit label reads held-out landings (R464).

    A landing is labelled stalled by looking `embargo` measured landings ahead, so the last
    `embargo` landings of the fit part carry labels built from the held-out part.

    Returns:
        The end of the fit part after the embargo, never below zero.

    """
    return max(0, held - embargo)


def score(
    landings: list[tuple[str, list[str], int]],
    spec: Spec = CODON,
    first: int = 0,
) -> dict[str, list[str]]:
    """Score both rules against what followed each landing.

    Args:
        landings: (sha, files touched, ratchet value after the landing), oldest first.
        spec: The ratchet's baseline file and measured prefixes.
        first: The index of the first landing to score; earlier landings still feed the
            windows, so a held-out part is judged by the history that really preceded it.

    Returns:
        The shas of the false oks and false behinds of each rule, under the keys
        `current false ok`, `current false behind`, `proposed false ok`,
        `proposed false behind`, and the key `scored` holding one sha per scored landing.

    """
    out: dict[str, list[str]] = {
        "current false ok": [],
        "current false behind": [],
        "proposed false ok": [],
        "proposed false behind": [],
        "scored": [],
    }
    every: list[int] = []
    counted: list[int] = []
    for at, (sha, files, value) in enumerate(landings):
        every.append(value)
        if measured(files, spec):
            counted.append(value)
        truth = stalled(landings, at, spec)
        if truth is None or at < first:
            continue
        out["scored"].append(sha)
        for name, series in (("current", every), ("proposed", counted)):
            said = verdict(series)
            if said == "ok" and truth:
                out[f"{name} false ok"].append(sha)
            if said == "behind" and not truth:
                out[f"{name} false behind"].append(sha)
    return out


Params = tuple[int, float, int]
# (windows looked back K, smoothing alpha, min_rate): the grid the fit searches (mtools:W2200)
GRID: list[Params] = [
    (k, alpha, floor) for k in (3, 5, 10) for alpha in (0.3, 0.6) for floor in (1, 2)
]


def paid_fraction(values: list[int], end: int, window: int = WINDOW) -> float:
    """Give the share of the value paid down over the window that ends before index `end`.

    Returns:
        The fall over the window divided by the value at its start (a rise counts as nothing);
        0.0 when there is not a full window of history.

    """
    if end <= window:
        return 0.0
    before = values[end - window - 1]
    return max(0, before - values[end - 1]) / max(1, before)


def learned_required(values: list[int], params: Params) -> int:
    """Learn the required fall: a share of the value, from how much recent windows really paid.

    The rate is an exponentially weighted mean of the paid fraction over the last K windows
    (newest weighted most), and the required fall is that share of the current value, never below
    min_rate (the smallest fall one landing can make: not zero, as ruled).

    Returns:
        The required fall for the next landing.

    """
    lookback, alpha, floor = params
    weighted = total = 0.0
    for age in range(lookback):
        end = len(values) - age
        if end <= WINDOW:
            break
        weight = (1 - alpha) ** age
        weighted += weight * paid_fraction(values, end)
        total += weight
    rate = weighted / total if total else 0.0
    return max(floor, int(-(-(rate * values[-1]) // 1)))


def verdict_learned(values: list[int], params: Params) -> str:
    """Judge a series under the learned required fall.

    Returns:
        `ok` or `behind`.

    """
    return "ok" if fall(values) >= learned_required(values, params) else "behind"


def score_learned(
    landings: list[tuple[str, list[str], int]],
    spec: Spec,
    params: Params,
    span: tuple[int, int],
) -> tuple[int, int, int]:
    """Score the learned rule against the stalled label over the landings in `span`.

    Args:
        landings: (sha, files touched, ratchet value after the landing), oldest first.
        spec: The ratchet's baseline file and measured prefixes.
        params: The rule's K, smoothing and min_rate.
        span: The first and one past the last landing index to score; earlier landings still
            feed the windows.

    Returns:
        (false oks, false behinds, landings scored).

    """
    every: list[int] = []
    false_ok = false_behind = scored = 0
    for at, (_sha, _files, value) in enumerate(landings):
        every.append(value)
        if not span[0] <= at < span[1]:
            continue
        truth = stalled(landings, at, spec)
        if truth is None:
            continue
        scored += 1
        said = verdict_learned(every, params)
        false_ok += said == "ok" and truth
        false_behind += said == "behind" and not truth
    return false_ok, false_behind, scored


def fit(
    landings: list[tuple[str, list[str], int]],
    spec: Spec,
    stop: int,
) -> Params:
    """Pick the grid point with the fewest errors on the fit part, landings before `stop`.

    Returns:
        The best (K, alpha, min_rate); the first of equals, so the choice is deterministic.

    """
    best, fewest = GRID[0], -1
    for params in GRID:
        false_ok, false_behind, _ = score_learned(landings, spec, params, (0, stop))
        errors = false_ok + false_behind
        if fewest < 0 or errors < fewest:
            best, fewest = params, errors
    return best


QParams = tuple[int, int, int]
# (paying windows kept K, lower quantile percent, min_rate): github-14's estimator (mtools:W2200)
QGRID: list[QParams] = [
    (k, pct, floor) for k in (5, 10, 20) for pct in (10, 25, 50) for floor in (1, 2)
]
FALSE_OK_WEIGHT = 2


def quantile_required(values: list[int], params: QParams) -> list[int]:
    """Learn, before each landing, the required fall from the windows that actually paid.

    The rate is a lower quantile of the share paid by the last K PAYING windows only (a stall adds
    nothing, so it cannot lower the rate), the required fall never falls, and it is capped by the
    most any recent paying window paid; it is never below min_rate.

    Returns:
        The required fall in force before each landing, from the windows that ended before it.

    """
    keep, pct, floor = params
    required: list[int] = []
    paid: list[tuple[int, int]] = []
    best = floor
    for at, value in enumerate(values):
        required.append(best)
        if at >= WINDOW and values[at - WINDOW] > value:
            paid.append((values[at - WINDOW] - value, values[at - WINDOW]))
            share, cap = lower_share(paid[-keep:], pct)
            best = max(best, min(cap, max(floor, int(-(-(share * value) // 1)))))
    return required


def lower_share(recent: list[tuple[int, int]], pct: int) -> tuple[float, int]:
    """Give the lower quantile of the shares the recent paying windows paid, and the cap.

    Args:
        recent: (fall, value at the window's start) for each recent paying window.
        pct: The percentile, 1 to 100, nearest rank.

    Returns:
        (the share at that percentile, the largest fall any of the windows paid).

    """
    shares = sorted(gained / max(1, start) for gained, start in recent)
    return (
        shares[max(0, (pct * len(shares) + 99) // 100 - 1)],
        max(gained for gained, _ in recent),
    )


MParams = tuple[int, int]
# (paying windows kept K, min_rate): option (b), a median of the paying windows (mtools:W2200)
MGRID: list[MParams] = [(k, floor) for k in (3, 5, 10, 20) for floor in (1, 2)]
SECONDS_PER_DAY = 86400


def median_required(values: list[int], params: MParams) -> list[int]:
    """Learn, before each landing, the required fall as a median of the paying windows' shares.

    A stalled window is not in the set, so a stall cannot lower the rate, and one burst cannot set
    it (a median ignores a single large window). Unlike the quantile estimator it may fall, but
    only when the repo's own recent paying windows get smaller; it is never below min_rate.

    Returns:
        The required fall in force before each landing, from the windows that ended before it.

    """
    keep, floor = params
    required: list[int] = []
    shares: list[float] = []
    best = floor
    for at, value in enumerate(values):
        required.append(best)
        if at >= WINDOW and values[at - WINDOW] > value:
            start = values[at - WINDOW]
            shares.append((start - value) / max(1, start))
            middle = sorted(shares[-keep:])
            best = max(floor, int(-(-(middle[len(middle) // 2] * value) // 1)))
    return required


def fit_median(
    landings: list[tuple[str, list[str], int]],
    spec: Spec,
    stop: int,
) -> MParams:
    """Pick the grid point with the lowest weighted error on the fit part, a false ok costing more.

    Returns:
        The best (K, min_rate); the first of equals, so the choice is deterministic.

    """
    values = [value for _sha, _files, value in landings]
    best, cheapest = MGRID[0], -1
    for params in MGRID:
        required = median_required(values, params)
        false_ok, false_behind, _ = score_admission(
            landings, spec, "learned", required, (0, stop)
        )
        cost = FALSE_OK_WEIGHT * false_ok + false_behind
        if cheapest < 0 or cost < cheapest:
            best, cheapest = params, cost
    return best


def days_to_zero(epochs: list[int], values: list[int], start: int) -> float:
    """Give the days the value would need to reach zero at the rate it fell from `start` to the end.

    This is the HISTORICAL rate, the same for every rule: a replay of landed commits cannot say
    what pace a rule would have produced (R470).

    Returns:
        Days at the observed rate, or -1.0 when the value did not fall or the span has no time.

    """
    days = (epochs[-1] - epochs[start]) / SECONDS_PER_DAY
    fell = values[start] - values[-1]
    if fell <= 0 or days <= 0:
        return -1.0
    return values[-1] / (fell / days)


def rose(landings: list[tuple[str, list[str], int]], at: int, spec: Spec) -> bool:
    """Say whether the value rose in the ten measured landings after landing `at`.

    A rise from an honest discovery is not a regression (operator, 2026-11-05), so a landing
    followed by one is not evidence against a rule that called it ok.

    Returns:
        True when any of the next ten measured values is above this landing's.

    """
    here = landings[at][2]
    later = [
        value for _sha, files, value in landings[at + 1 :] if measured(files, spec)
    ]
    return any(value > here for value in later[:WINDOW])


def admission(rule: str, every: list[int], counted: list[int], required: int) -> str:
    """Say what a rule would do with a landing that pays nothing, from the state before it.

    Args:
        rule: `current` (the last ten landings), `window` (the last ten measured landings) or
            `learned` (the last ten landings against a learned required fall).
        every: The ratchet's value after each earlier landing.
        counted: The same, for earlier landings the ratchet measures.
        required: The learned required fall in force before this landing.

    Returns:
        `ok` (admit a landing that pays nothing) or `behind` (refuse it).

    """
    if rule == "current":
        return verdict(every)
    if rule == "window":
        return verdict(counted)
    return "ok" if fall(every) >= required else "behind"


def score_admission(
    landings: list[tuple[str, list[str], int]],
    spec: Spec,
    rule: str,
    required: list[int],
    span: tuple[int, int],
) -> tuple[int, int, int]:
    """Score a rule as an admission rule, over the landings in `span` that paid nothing.

    A landing that lowers the value is always admitted, so only a landing that pays nothing can be
    wrongly admitted (a false ok: it was followed by a stall) or wrongly refused (a false behind:
    the value fell soon anyway). A landing followed by a rise is left out.

    Returns:
        (false oks, false behinds, landings scored).

    """
    every: list[int] = []
    counted: list[int] = []
    false_ok = false_behind = scored = 0
    for at, (_sha, files, value) in enumerate(landings):
        pays = bool(every) and value < every[-1]
        in_span = span[0] <= at < span[1]
        truth = stalled(landings, at, spec) if in_span and not pays else None
        if truth is not None and not rose(landings, at, spec):
            said = admission(rule, every, counted, required[at])
            scored += 1
            false_ok += said == "ok" and truth
            false_behind += said == "behind" and not truth
        every.append(value)
        if measured(files, spec):
            counted.append(value)
    return false_ok, false_behind, scored


def fit_quantile(
    landings: list[tuple[str, list[str], int]],
    spec: Spec,
    stop: int,
) -> QParams:
    """Pick the grid point with the lowest weighted error on the fit part, a false ok costing more.

    Returns:
        The best (K, percent, min_rate); the first of equals, so the choice is deterministic.

    """
    values = [value for _sha, _files, value in landings]
    best, cheapest = QGRID[0], -1
    for params in QGRID:
        required = quantile_required(values, params)
        false_ok, false_behind, _ = score_admission(
            landings, spec, "learned", required, (0, stop)
        )
        cost = FALSE_OK_WEIGHT * false_ok + false_behind
        if cheapest < 0 or cost < cheapest:
            best, cheapest = params, cost
    return best


def split_log(text: str) -> list[tuple[str, int, list[str]]]:
    """Split `git log --format="@%h %ct" --name-only` output into (sha, epoch, files) per commit.

    Returns:
        One triple per commit, in the order printed; the epoch is 0 when the line carries none.

    """
    out: list[tuple[str, int, list[str]]] = []
    sha, epoch = "", 0
    files: list[str] = []
    for line in [*text.splitlines(), "@"]:
        if line.startswith("@"):
            if sha:
                out.append((sha, epoch, files))
            head = line[1:].split()
            sha = head[0] if head else ""
            epoch = int(head[1]) if len(head) > 1 and head[1].isdigit() else 0
            files = []
        elif line.strip():
            files.append(line.strip())
    return out


def read_landings(
    repo: Path,
    spec: Spec = CODON,
    unit: str = "entries",
) -> list[tuple[str, int, list[str], int]]:
    """Read main's landings, oldest first: epoch, files touched and the ratchet value after each.

    Args:
        repo: The repository to read.
        spec: The ratchet's baseline file and measured prefixes.
        unit: `entries` (codon modes), `pairs` (file and rule pairs) or `counts` (summed counts).

    Returns:
        (sha, epoch, files, value) per landing; the value is carried forward from the last
        landing that changed the baseline.

    """
    baseline = spec[0]
    count = {"entries": entries, "pairs": pairs, "counts": counts}[unit]
    log = capture(["git", "-C", str(repo), *LOG_ARGS])
    value = 0
    filled: list[tuple[str, int, list[str], int]] = []
    for sha, epoch, files in split_log(log.stdout):
        if baseline in files:
            shown = capture(["git", "-C", str(repo), "show", f"{sha}:{baseline}"])
            value = count(shown.stdout) if shown.returncode == 0 else value
        filled.append((sha, epoch, files, value))
    return filled


def row_values(text: str, unit: str) -> dict[str, int]:
    """Give each row of a baseline document its own value: `counts` sums, else entries.

    Returns:
        The value of each top-level row (a file or a module), keyed by its name; a row that is
        not an object is 0, as in `pairs` and `counts`.

    """
    table = _document(text)
    if unit == "counts":
        return {
            name: sum(v for v in _table(row).values() if isinstance(v, int))
            for name, row in table.items()
        }
    return {name: len(_table(row)) for name, row in table.items()}


def read_rows(
    repo: Path, spec: Spec = CODON, unit: str = "entries"
) -> list[tuple[str, int, list[str], dict[str, int]]]:
    """Read main's landings, oldest first, with the value of every row after each.

    Returns:
        (sha, epoch, files, rows) per landing; the rows are carried forward from the last landing
        that changed the baseline, as `read_landings` carries the total.

    """
    baseline = spec[0]
    log = capture(["git", "-C", str(repo), *LOG_ARGS])
    rows: dict[str, int] = {}
    filled: list[tuple[str, int, list[str], dict[str, int]]] = []
    for sha, epoch, files in split_log(log.stdout):
        if baseline in files:
            shown = capture(["git", "-C", str(repo), "show", f"{sha}:{baseline}"])
            rows = row_values(shown.stdout, unit) if shown.returncode == 0 else rows
        filled.append((sha, epoch, files, rows))
    return filled


def row_series(rows: list[dict[str, int]]) -> dict[str, list[int]]:
    """Turn the rows after each landing into one series per row; a row not there yet is 0.

    Returns:
        For each row name that ever appears, its value after each landing.

    """
    names = sorted({name for row in rows for name in row})
    return {name: [row.get(name, 0) for row in rows] for name in names}


def stalled_rows(series: dict[str, list[int]], at: int) -> list[str]:
    """Name the rows still owing something at landing `at` that did not fall in the last window.

    Returns:
        The rows whose value at `at` is above zero and whose fall over the window ending there
        is zero or less.

    """
    return [
        name
        for name, values in sorted(series.items())
        if values[at] > 0 and fall(values[: at + 1]) <= 0
    ]


NEGLECT_PERCENTS = (50, 75, 90)


def row_ages(values: list[int]) -> list[int]:
    """Give, per landing, the landings since the row last fell, or since it appeared.

    A row that has never fallen is aged from its appearance (right-censored), so a row nobody
    touches still has an age.

    Returns:
        The age after each landing; it is 0 on the landing of a fall or of an appearance.

    """
    ages: list[int] = []
    last = 0
    for at, value in enumerate(values):
        before = values[at - 1] if at else 0
        if value < before or (before == 0 and value > 0):
            last = at
        ages.append(at - last)
    return ages


def row_gaps(values: list[int]) -> list[tuple[int, int]]:
    """Give each completed wait of a row: the landing of a fall and the landings it had waited.

    Returns:
        (index of the fall, landings since the previous fall or since the row appeared).

    """
    gaps: list[tuple[int, int]] = []
    last = 0
    for at, value in enumerate(values):
        before = values[at - 1] if at else 0
        if value < before:
            gaps.append((at, at - last))
            last = at
        elif before == 0 and value > 0:
            last = at
    return gaps


def learned_wait(gaps: list[tuple[int, int]], at: int, percent: int) -> int:
    """Give the percentile of the waits completed at or before landing `at`.

    Returns:
        The learned wait N, or -1 when no wait has completed yet (nothing can be neglected).

    """
    seen = sorted(gap for index, gap in gaps if index <= at)
    if not seen:
        return -1
    return seen[min(len(seen) - 1, len(seen) * percent // 100)]


def neglected_rows(series: dict[str, list[int]], percent: int) -> list[list[str]]:
    """Name, after each landing, the owing rows whose age is above the wait learned so far.

    The wait is a percentile of every row's completed waits in the same series, recomputed as the
    history grows, never a constant.

    Returns:
        One list of row names per landing.

    """
    pooled = [gap for values in series.values() for gap in row_gaps(values)]
    ages = {name: row_ages(values) for name, values in series.items()}
    count = len(next(iter(series.values()), []))
    out: list[list[str]] = []
    for at in range(count):
        wait = learned_wait(pooled, at, percent)
        out.append(
            [
                name
                for name, values in sorted(series.items())
                if wait >= 0 and values[at] > 0 and ages[name][at] > wait
            ]
        )
    return out


def score_neglect(
    landings: list[tuple[str, list[str], int]],
    neglected: list[list[str]],
    spec: Spec,
    span: tuple[int, int],
) -> tuple[int, int, int]:
    """Score the neglect rule as an admission rule over the landings in `span` that paid nothing.

    A landing is refused when some row was neglected before it and the landing touches none of
    them; touching a neglected row is the way out. Scored as `score_admission` scores.

    Returns:
        (false oks, false behinds, landings scored).

    """
    false_ok = false_behind = scored = 0
    for at, (_sha, files, value) in enumerate(landings):
        if at == 0 or not span[0] <= at < span[1] or value < landings[at - 1][2]:
            continue
        truth = stalled(landings, at, spec)
        if truth is None or rose(landings, at, spec):
            continue
        blocked = bool(neglected[at - 1]) and not set(neglected[at - 1]) & set(files)
        scored += 1
        false_ok += not blocked and truth
        false_behind += blocked and not truth
    return false_ok, false_behind, scored


BOUNDS = (0, 10, 25, 50, 75)
Bound = tuple[int, int]


def neglected_share(
    series: dict[str, list[int]], neglected: list[list[str]]
) -> list[float]:
    """Give, after each landing, the share of the owing rows that are neglected.

    Returns:
        Neglected rows over owing rows per landing; 0.0 when no row is owing.

    """
    count = len(neglected)
    owing = [
        sum(1 for values in series.values() if values[at] > 0) for at in range(count)
    ]
    return [len(neglected[at]) / owing[at] if owing[at] else 0.0 for at in range(count)]


def bounded_blocks(
    landings: list[tuple[str, list[str], int]],
    neglected: list[list[str]],
    shares: list[float],
    bound: int,
) -> list[bool]:
    """Say, per landing, whether the bounded neglect rule refuses it if it pays nothing.

    A landing is refused when the neglected share before it is above `bound` percent and it
    touches none of the neglected rows (touching one is the way out).

    Returns:
        One flag per landing; the first is never refused.

    """
    return [
        at > 0
        and shares[at - 1] * 100 > bound
        and not set(neglected[at - 1]) & set(landings[at][1])
        for at in range(len(landings))
    ]


def score_blocks(
    landings: list[tuple[str, list[str], int]],
    blocks: list[bool],
    spec: Spec,
    span: tuple[int, int],
) -> tuple[int, int, int]:
    """Score refusals as `score_admission` scores a rule: only a landing that paid nothing.

    Returns:
        (false oks, false behinds, landings scored).

    """
    false_ok = false_behind = scored = 0
    for at, (_sha, _files, value) in enumerate(landings):
        if at == 0 or not span[0] <= at < span[1] or value < landings[at - 1][2]:
            continue
        truth = stalled(landings, at, spec)
        if truth is None or rose(landings, at, spec):
            continue
        scored += 1
        false_ok += not blocks[at] and truth
        false_behind += blocks[at] and not truth
    return false_ok, false_behind, scored


def fit_bound(
    landings: list[tuple[str, list[str], int]],
    by_percent: dict[int, tuple[list[list[str]], list[float]]],
    spec: Spec,
    stop: int,
) -> Bound:
    """Pick the (percentile of waits, bound on the neglected share) with the lowest weighted error.

    Fitted on the landings before `stop` only, a false ok costing `FALSE_OK_WEIGHT` false behinds.

    Returns:
        The best (percent, bound); the first of equals, so the choice is deterministic.

    """
    best: Bound = (NEGLECT_PERCENTS[0], BOUNDS[0])
    cheapest = -1
    for percent in NEGLECT_PERCENTS:
        neglected, shares = by_percent[percent]
        for bound in BOUNDS:
            blocks = bounded_blocks(landings, neglected, shares, bound)
            ok, behind, _scored = score_blocks(landings, blocks, spec, (0, stop))
            cost = FALSE_OK_WEIGHT * ok + behind
            if cheapest < 0 or cost < cheapest:
                best, cheapest = (percent, bound), cost
    return best


def trajectory(
    landings: list[tuple[str, list[str], int]],
    blocks: list[bool],
    shares: list[float],
    span: tuple[int, int],
) -> str:
    """Describe the held-out span under the bounded rule: refusals and what admissions paid.

    Returns:
        One line: the landings that paid nothing and were refused, the first landing after which
        the neglected share is zero (or none), and the fall of each landing that paid, summed.

    """
    refused = [
        at
        for at in range(*span)
        if blocks[at] and landings[at][2] >= landings[at - 1][2]
    ]
    paid = [
        landings[at - 1][2] - landings[at][2]
        for at in range(*span)
        if landings[at][2] < landings[at - 1][2]
    ]
    clear = next((at for at in range(*span) if shares[at] <= 0), None)
    return (
        f"held-out landings {span[1] - span[0]}: refused (paid nothing) {len(refused)}, "
        f"last refused {refused[-1] if refused else 'none'}; neglected share first zero at "
        f"{clear if clear is not None else 'never'}; landings that paid {len(paid)}, "
        f"total fall {sum(paid)}, per paying landing "
        f"{sum(paid) / len(paid) if paid else 0.0:.2f}"
    )


def landings_to_zero(values: list[int], start: int) -> float:
    """Give the landings a row would need to reach zero at the rate it fell from `start`.

    Returns:
        Landings at the observed rate, or -1.0 when the row did not fall.

    """
    return days_to_zero(
        [i * SECONDS_PER_DAY for i in range(len(values))], values, start
    )


def report_rows(name: str, series: dict[str, list[int]], held: int) -> None:
    """Print how many rows are owing and how many stand still, at the held-out start and the end."""
    last = len(next(iter(series.values()), [])) - 1
    if last < 0:
        return
    sys.stdout.write(f"rows of {name}:")
    for label, at in (("held-out start", held), ("end", last)):
        owing = [n for n, values in series.items() if values[at] > 0]
        sys.stdout.write(
            f" {label}: {len(owing)} owing, {len(stalled_rows(series, at))} stalled;"
        )
    sys.stdout.write("\n")


def report_neglect(
    name: str,
    landings: list[tuple[str, list[str], int]],
    series: dict[str, list[int]],
    spec: Spec,
) -> None:
    """Print the held-out score of the neglect rule at each learned percentile."""
    held = held_start(len(landings))
    for percent in NEGLECT_PERCENTS:
        neglected = neglected_rows(series, percent)
        ok, behind, scored = score_neglect(
            landings, neglected, spec, (held, len(landings))
        )
        sys.stdout.write(
            f"neglect of {name} at the {percent}th percentile of waits: false ok {ok}, "
            f"false behind {behind} (scored {scored}); neglected rows at the end "
            f"{len(neglected[-1]) if neglected else 0}\n"
        )
    owing = [values for values in series.values() if values and values[-1] > 0]
    moving = [v for v in owing if landings_to_zero(v, held) >= 0]
    sys.stdout.write(
        f"rows owing at the end: {len(owing)}, of which fell over the held-out span "
        f"{len(moving)} and did not {len(owing) - len(moving)}\n"
    )


def report_bound(
    name: str,
    landings: list[tuple[str, list[str], int]],
    series: dict[str, list[int]],
    spec: Spec,
) -> None:
    """Print the bounded neglect rule fitted before the embargo and judged held-out."""
    held = held_start(len(landings))
    by_percent: dict[int, tuple[list[list[str]], list[float]]] = {}
    for percent in NEGLECT_PERCENTS:
        neglected = neglected_rows(series, percent)
        by_percent[percent] = (neglected, neglected_share(series, neglected))
    percent, bound = fit_bound(landings, by_percent, spec, fit_end(held))
    neglected, shares = by_percent[percent]
    blocks = bounded_blocks(landings, neglected, shares, bound)
    ok, behind, scored = score_blocks(landings, blocks, spec, (held, len(landings)))
    sys.stdout.write(
        f"bounded neglect of {name}, fitted before landing {fit_end(held)}: wait at the "
        f"{percent}th percentile, bound {bound} percent; held-out false ok {ok}, false "
        f"behind {behind} (scored {scored})\n"
        f"  {trajectory(landings, blocks, shares, (held, len(landings)))}\n"
    )


def report_admission(
    landings: list[tuple[str, list[str], int]], spec: Spec, held: int
) -> None:
    """Print the held-out admission score of the current, window, quantile and median rules."""
    values = [v for _s, _f, v in landings]
    quantile = fit_quantile(landings, spec, fit_end(held))
    median = fit_median(landings, spec, fit_end(held))
    sys.stdout.write(
        f"admission (a landing that paid nothing), held-out, a false ok weighted "
        f"{FALSE_OK_WEIGHT}x in the fit; quantile estimator K {quantile[0]}, lower "
        f"{quantile[1]} percent, min_rate {quantile[2]}; median estimator K {median[0]}, "
        f"min_rate {median[1]}\n"
    )
    span = (held, len(landings))
    for label, rule, required in (
        ("current", "current", []),
        ("window", "window", []),
        ("quantile", "learned", quantile_required(values, quantile)),
        ("median", "learned", median_required(values, median)),
    ):
        ok, behind, scored = score_admission(
            landings, spec, rule, required or [0] * len(landings), span
        )
        sys.stdout.write(
            f"  {label}: false ok {ok}, false behind {behind} (scored {scored})\n"
        )


def report_series(
    name: str, landings: list[tuple[str, list[str], int]], spec: Spec
) -> None:
    """Print one series: where the rules differ, their all-history score and the held-out ones."""
    result = score(landings, spec)
    sys.stdout.write(
        f"== {name}: landings {len(landings)}, differing {len(replay(landings, spec))}\n"
        f"scored {len(result['scored'])}\n"
    )
    for key, shas in result.items():
        if key != "scored":
            sys.stdout.write(f"{key}: {len(shas)}\n")
    held = held_start(len(landings))
    out = score(landings, spec, held)
    sys.stdout.write(
        f"held-out from landing {held} (fit part ends at {fit_end(held)} after the "
        f"embargo): scored {len(out['scored'])}; current false ok "
        f"{len(out['current false ok'])}, false behind {len(out['current false behind'])}; "
        f"proposed false ok {len(out['proposed false ok'])}, false behind "
        f"{len(out['proposed false behind'])}\n"
    )
    params = fit(landings, spec, fit_end(held))
    learned = score_learned(landings, spec, params, (held, len(landings)))
    sys.stdout.write(
        f"learned required, fitted before landing {fit_end(held)}: K {params[0]}, "
        f"alpha {params[1]}, min_rate {params[2]}; held-out false ok {learned[0]}, "
        f"false behind {learned[1]} (scored {learned[2]})\n"
    )
    report_admission(landings, spec, held)


def main() -> int:
    """Print, per series, the landings where the rules differ and the score of each rule.

    Returns:
        0.

    """
    repo = Path(__file__).resolve().parents[1]
    runs = (
        ("codon entries", CODON, "entries"),
        ("ruff pairs", RUFF, "pairs"),
        ("ruff counts", RUFF, "counts"),
        ("mypy pairs", MYPY, "pairs"),
        ("mypy counts", MYPY, "counts"),
    )
    for name, spec, unit in runs:
        full = read_landings(repo, spec, unit)
        landings = [(sha, files, value) for sha, _epoch, files, value in full]
        report_series(name, landings, spec)
        epochs = [epoch for _sha, epoch, _files, _value in full]
        values = [value for _sha, _files, value in landings]
        days = days_to_zero(epochs, values, held_start(len(landings)))
        sys.stdout.write(
            f"historical days to zero over the held-out span (no rule's effect): {days:.1f}\n"
        )
        per_row = read_rows(repo, spec, unit)
        rows_by_name = row_series([rows for _sha, _epoch, _files, rows in per_row])
        report_rows(name, rows_by_name, held_start(len(per_row)))
        report_neglect(name, landings, rows_by_name, spec)
        report_bound(name, landings, rows_by_name, spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
