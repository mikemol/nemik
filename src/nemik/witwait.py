"""nemik:W258: wait on a witness, so a session can background it and get one notification.

    nemik-witnesses --wait '<PromQL expression, or a Rego query over the observers>' --timeout 12h

The evaluator is the one `nemik-witnesses` already has, over the same closed set of observers, run
in a loop. Three outcomes, and unknown is not false:

- exit 0: it holds. Prints the observed value and when it first held.
- exit 1: the timeout passed and the last poll said "not yet". Prints that last observed value
  (never an empty line: an empty PromQL result is said to be empty).
- exit 2: it cannot be evaluated: the probe is unreachable, the endpoint is unset, or the query is
  bad. A few consecutive unknown polls are tolerated (a probe can blip during a twelve-hour wait);
  more than `TOLERATE`, or an unknown last poll at the timeout, is exit 2.

A bare PromQL expression holds when its instant-query result is non-empty, the PromQL meaning of a
comparison (`x > 0.99` returns the series only while it is true). A query that names `input.<observer>`
is Rego, decided by opa as for a waypoint witness.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from nemik.witnesses import _REF, _get, witness

if TYPE_CHECKING:
    from collections.abc import Callable

HELD, NOT_YET, UNKNOWN = "held", "not-yet", "unknown"
EXIT_HELD, EXIT_TIMEOUT, EXIT_UNKNOWN = 0, 1, 2
TOLERATE = 3
_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_DURATION = re.compile(r"(\d+)([smhd])")


def seconds(text: str) -> float:
    """Read a duration such as `90s`, `30m`, `12h` or `1d`.

    Returns:
        the number of seconds.

    Raises:
        ValueError: when the text is not a whole number and one of s, m, h, d.

    """
    m = _DURATION.fullmatch(text.strip())
    if m is None:
        msg = f"not a duration (use 90s, 30m, 12h or 1d): {text!r}"
        raise ValueError(msg)
    return float(int(m[1]) * _SECONDS[m[2]])


def rego_poll(query: str) -> Callable[[], tuple[str, str]]:
    """Poll a Rego witness over the observers.

    Returns:
        a function giving (state, what was seen).

    """

    def poll() -> tuple[str, str]:
        verdict, doc, missing = witness(query)
        seen = json.dumps({k: v for k, v in doc.items() if k != "now"}, sort_keys=True)
        if verdict == "true":
            return HELD, seen
        if verdict == "false":
            return NOT_YET, seen
        return UNKNOWN, f"cannot observe {', '.join(missing) or 'the query'}"

    return poll


def promql_poll(expr: str) -> Callable[[], tuple[str, str]]:
    """Poll a PromQL instant query; it holds while the result is non-empty.

    Returns:
        a function giving (state, what was seen).

    """

    def poll() -> tuple[str, str]:
        body = _get("NEMIK_VM_URL", "/api/v1/query", {"query": expr})
        if body is None:
            return UNKNOWN, "probe unreachable, or NEMIK_VM_URL is unset"
        try:
            values = [float(r["value"][1]) for r in body["data"]["result"]]
        except (KeyError, IndexError, TypeError, ValueError):
            return UNKNOWN, "the probe returned a result nemik cannot read"
        if values:
            keep = 5  # a wait prints a readable value, not forty-nine series
            shown = ", ".join(f"{v:g}" for v in values[:keep])
            more = f" (+{len(values) - keep} more series)" if len(values) > keep else ""
            return HELD, shown + more
        return NOT_YET, "empty result (the expression is false, or no series)"

    return poll


def poller(query: str) -> Callable[[], tuple[str, str]]:
    """Choose the evaluator for a query: Rego when it names an observer, else PromQL.

    Returns:
        the poll function.

    """
    return rego_poll(query) if _REF.search(query) else promql_poll(query)


def wait(
    poll: Callable[[], tuple[str, str]],
    timeout_s: float,
    every_s: float,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    stamp: Callable[[], str] = lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
) -> tuple[int, str]:
    """Poll until the witness holds, the timeout passes, or it cannot be evaluated.

    Returns:
        (exit code, the one line to print).

    """
    deadline = clock() + timeout_s
    last, unknowns = "never observed", 0
    while True:
        state, seen = poll()
        if state == HELD:
            return EXIT_HELD, f"HELD at {stamp()}: {seen}"
        unknowns = unknowns + 1 if state == UNKNOWN else 0
        last = seen
        if unknowns > TOLERATE:
            return EXIT_UNKNOWN, f"UNKNOWN after {unknowns} polls: {seen}"
        if clock() + every_s > deadline:
            if unknowns:
                return EXIT_UNKNOWN, f"UNKNOWN at the timeout: {last}"
            return EXIT_TIMEOUT, f"TIMEOUT, last value: {last}"
        sleep(every_s)
