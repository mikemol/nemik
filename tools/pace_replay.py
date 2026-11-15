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


def main() -> int:
    """Print the landings where the rules differ, then the score of each rule.

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
        differing = replay(landings, spec)
        head = f"== {name}: landings {len(landings)}, differing {len(differing)}\n"
        sys.stdout.write(head)
        result = score(landings, spec)
        sys.stdout.write(f"scored {len(result['scored'])}\n")
        for key, shas in result.items():
            if key != "scored":
                sys.stdout.write(f"{key}: {len(shas)}\n")
        shown = " ".join(result["proposed false ok"][:SHOWN])
        sys.stdout.write(f"proposed false ok (first {SHOWN}): {shown}\n")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
