# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W662: luthen's loop and token series, read from the snapshot in the export tree.

luthen-observability writes luthen-series.json beside withheld.json (luthen:W1295):
{"version": 1, "as_of": epoch, "liveness": {repo: {"verdict", "last_tick" (absent when
none), "history": [[epoch, verdict], ...]}}, "tokens": [{"repo", "session", "kind",
"value"}]}. The pod holds no key material, so it reads this file and never queries the
store. A file that is missing, unversioned or older than the bound is refused, the way
--withheld-max-age refuses withheld.json, because a board drawn from a stopped producer
would read as live. docs/luthen-series.md has the design.
"""

import json
from pathlib import Path

VERSION = 1
NO_TICK = -1
PAIR = 2


class Repo:
    """One repo's loop, as luthen last saw it."""

    def __init__(
        self, verdict: str, last_tick: int, stamps: list[int], verdicts: list[str]
    ) -> None:
        """Hold one repo's loop.

        Args:
            verdict: luthen's current verdict.
            last_tick: The last tick, epoch seconds, or NO_TICK.
            stamps: When each history row was taken, oldest first.
            verdicts: The verdict at each stamp.

        """
        self.verdict = verdict
        self.last_tick = last_tick
        self.stamps = stamps
        self.verdicts = verdicts

    def verdict_at(self, when: int) -> str:
        """Name the verdict in force at a time.

        Args:
            when: Epoch seconds.

        Returns:
            The verdict of the latest history row at or before it; empty before the first.

        """
        found = ""
        for i in range(len(self.stamps)):
            if self.stamps[i] <= when:
                found = self.verdicts[i]
        return found


class Token:
    """One session's cumulative token count of one kind."""

    def __init__(self, repo: str, session: str, kind: str, value: int) -> None:
        """Hold one count.

        Args:
            repo: The repo whose project the session ran in.
            session: The transcript's UUID.
            kind: input, output, cache_create or cache_read.
            value: Tokens since the session began.

        """
        self.repo = repo
        self.session = session
        self.kind = kind
        self.value = value

    def counts_for(self, repo: str, kind: str) -> bool:
        """Say whether this count belongs to a repo and kind.

        Args:
            repo: The repo.
            kind: The token kind.

        Returns:
            True when both match.

        """
        return self.repo == repo and self.kind == kind


class Series:
    """The whole snapshot."""

    def __init__(self, as_of: int, repos: dict[str, Repo], tokens: list[Token]) -> None:
        """Hold the snapshot.

        Args:
            as_of: When luthen wrote it, epoch seconds.
            repos: Each repo's loop by name.
            tokens: Every session's counts.

        """
        self.as_of = as_of
        self.repos = repos
        self.tokens = tokens

    def total(self, repo: str, kind: str) -> int:
        """Sum a repo's sessions' tokens of one kind.

        Args:
            repo: The repo.
            kind: The token kind.

        Returns:
            The sum; 0 when no session counts.

        """
        return sum(t.value for t in self.tokens if t.counts_for(repo, kind))


def _mapping(value: object, what: str) -> dict[str, object]:
    """Require a JSON object.

    Args:
        value: What was parsed.
        what: Where it sat, for the refusal.

    Returns:
        The object with string keys.

    Raises:
        TypeError: When it is not an object.

    """
    if not isinstance(value, dict):
        message = what + " is not an object"
        raise TypeError(message)
    return {str(k): v for k, v in value.items()}


def _number(value: object, what: str) -> int:
    """Require a whole number of seconds or tokens.

    Args:
        value: What was parsed.
        what: Where it sat, for the refusal.

    Returns:
        The number.

    Raises:
        TypeError: When it is not a number.

    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value)
    message = what + " is not a number"
    raise TypeError(message)


def _repo(body: object, name: str) -> Repo:
    """Read one repo's liveness entry.

    Args:
        body: The entry.
        name: The repo, for the refusal.

    Returns:
        The repo; last_tick is NO_TICK when the entry has none.

    """
    entry = _mapping(body, "liveness." + name)
    last = entry.get("last_tick")
    tick = NO_TICK if last is None else _number(last, "last_tick of " + name)
    stamps: list[int] = []
    verdicts: list[str] = []
    rows: object = entry.get("history", [])
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list) and len(row) == PAIR:
                stamps.append(_number(row[0], "a history stamp"))
                verdicts.append(str(row[1]))
    return Repo(str(entry.get("verdict", "")), tick, stamps, verdicts)


def _token(row: object) -> Token:
    """Read one tokens row.

    Args:
        row: The row.

    Returns:
        The token count.

    """
    item = _mapping(row, "a tokens row")
    value = _number(item.get("value"), "a tokens value")
    return Token(
        str(item.get("repo")), str(item.get("session")), str(item.get("kind")), value
    )


def parse(text: str, now: int, max_age: int) -> Series:
    """Read a snapshot, refusing one that cannot be trusted.

    Args:
        text: The file's text.
        now: The current epoch seconds.
        max_age: The oldest as_of accepted, in seconds.

    Returns:
        The series.

    Raises:
        ValueError: When the file is unversioned or its as_of is older than max_age or
            from the future.

    """
    parsed: object = json.loads(text)
    top = _mapping(parsed, "the file")
    if top.get("version") != VERSION:
        message = "version is not " + str(VERSION)
        raise ValueError(message)
    as_of = _number(top.get("as_of"), "as_of")
    age = now - as_of
    if age < 0 or age > max_age:
        message = "as_of is " + str(age) + " s old, outside 0.." + str(max_age)
        raise ValueError(message)
    repos: dict[str, Repo] = {}
    live = _mapping(top.get("liveness", {}), "liveness")
    for name in live:
        repos[name] = _repo(live[name], name)
    rows: object = top.get("tokens", [])
    tokens = [_token(row) for row in rows] if isinstance(rows, list) else []
    return Series(as_of, repos, tokens)


def load(path: Path, now: int, max_age: int) -> Series:
    """Read the snapshot file.

    Args:
        path: luthen-series.json.
        now: The current epoch seconds.
        max_age: The oldest as_of accepted, in seconds.

    Returns:
        The series.

    """
    return parse(path.read_text(encoding="utf-8"), now, max_age)


def state_of(verdict: str) -> str:
    """Say whether a repo is awake, idle or asleep, from luthen's verdict.

    The same reading nemik.wake makes of loop_liveness (its AWAKE table), kept here so this
    module needs nothing else: a live session ticking is awake ("ok"), no live session is asleep
    ("dormant"), and any other verdict (stale, or one luthen adds later) is idle.

    Args:
        verdict: The repo's verdict as luthen names it.

    Returns:
        "awake", "asleep" or "idle".

    """
    if verdict == "ok":
        return "awake"
    return "asleep" if verdict == "dormant" else "idle"


def stranded(series: Series, ready: dict[str, int]) -> list[str]:
    """List the repos that hold workable cards but are not awake.

    Args:
        series: The snapshot.
        ready: How many cards are ready or working in each repo's queue.

    Returns:
        The repos with work and a state other than awake, asleep ones and then idle ones,
        each group in name order.

    """
    asleep: list[str] = []
    idle: list[str] = []
    for name in sorted(series.repos):
        state = state_of(series.repos[name].verdict)
        if ready.get(name, 0) > 0 and state == "asleep":
            asleep.append(name)
        elif ready.get(name, 0) > 0 and state == "idle":
            idle.append(name)
    return asleep + idle


def board(series: Series, ready: dict[str, int]) -> dict[str, object]:
    """Lay the snapshot out as the document the view draws.

    Args:
        series: The snapshot.
        ready: How many cards are ready or working in each repo's queue.

    Returns:
        {"as_of", "repos", "stranded"}: per repo its state, luthen's verdict, last tick (NO_TICK
        when none), how many cards are ready, and its history as {at, state} rows; and the
        repos that hold work but are not awake.

    """
    repos: dict[str, object] = {}
    for name in sorted(series.repos):
        repo = series.repos[name]
        rows: list[dict[str, object]] = [
            {"at": repo.stamps[i], "state": state_of(repo.verdicts[i])}
            for i in range(len(repo.stamps))
        ]
        repos[name] = {
            "state": state_of(repo.verdict),
            "verdict": repo.verdict,
            "last_tick": repo.last_tick,
            "ready": ready.get(name, 0),
            "history": rows,
        }
    return {
        "as_of": series.as_of,
        "repos": repos,
        "stranded": stranded(series, ready),
    }
