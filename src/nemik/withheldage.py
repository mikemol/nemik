# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W647: refuse a withheld list that has stopped being refreshed.

luthen restamps `as_of` on every successful run of its egress gate (every minute) and removes the
file on a refusal, so the age of `as_of` says whether the producer is still running. A list older
than a bound is not the current list: a card that became sensitive since would be published. This
reads only `as_of`, so nemik.withheld's parsing is untouched and the check is opt-in.
"""

import json
from datetime import datetime
from pathlib import Path

from nemik.withheld import WithheldError

SKEW = 300  # seconds a stamp may sit in the future before the clocks are suspect
STOPPED = "its producer has stopped, so it may miss a card that must not pass"


def _stamp(path: Path) -> str:
    """Read the list's as_of text.

    Args:
        path: The withheld list.

    Returns:
        The as_of string, or a sentence beginning "!" saying why there is none.

    """
    try:
        doc: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as err:
        return f"!cannot read it: {err}"
    except ValueError as err:
        return f"!not JSON: {err}"
    stamp: object = doc.get("as_of") if isinstance(doc, dict) else None
    return stamp if isinstance(stamp, str) else "!no as_of to date it by"


def problem(path: Path, max_age: int, now: float) -> str:
    """Say what is wrong with a list's freshness, if anything.

    Args:
        path: The withheld list.
        max_age: The oldest as_of allowed, in seconds.
        now: The current time, seconds since the epoch.

    Returns:
        A sentence naming the fault, or "" when the list is fresh: it is unreadable, has no usable
        as_of, is older than `max_age`, or is further in the future than SKEW.

    """
    stamp = _stamp(path)
    if stamp.startswith("!"):
        return stamp[1:]
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return f"as_of {stamp!r} is not a time"
    if moment.tzinfo is None:
        return f"as_of {stamp!r} has no offset"
    age = now - moment.timestamp()
    if age > max_age:
        return f"is {int(age)} s old (limit {max_age} s): {STOPPED}"
    if age < -SKEW:
        return f"as_of {stamp!r} is in the future"
    return ""


def require_fresh(path: Path, max_age: int, now: float) -> None:
    """Refuse a list that is stale, undated or unreadable.

    Args:
        path: The withheld list.
        max_age: The oldest as_of allowed, in seconds.
        now: The current time, seconds since the epoch.

    Raises:
        WithheldError: The list is not fresh; the message says why.

    """
    why = problem(path, max_age, now)
    if why:
        message = f"withheld list {path}: {why}"
        raise WithheldError(message)
