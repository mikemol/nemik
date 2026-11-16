# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W577: an idle loop, a repo that ticks and advances nothing while it has no workable card.

linux-sources ticked "no change" every half hour for days while its one open card waited on a
cycle nobody could see (nemik:W576). A loop with nothing ready and nothing working that keeps
reporting idle is paying for a clock: it should disarm, or name what it waits for in a blocked
card so a peer can see the edge. The count N (in ticks) and the outcomes that mean "idle" are
declared in rank-weights.toml under [idle]; this module holds only the reading of them.

nemik:W676 adds the other way a loop drifts: a session that has not acknowledged a change to the
canonical loop prompt. mtools keeps each repo's last acknowledged reading beside its git directory
(`.git/mtools/loop-prompt.seen`, written by --prompt-ack) and the prompt lives at
`~/github/.claude/loop-prompt.md`; a repo whose reading differs from the prompt is behind.
"""

import json
import time
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

from nemik.adapter import BASE, NEMIK, OSLC_CM, ledger_rows, tick_outcomes
from nemik.tomlview import table

if TYPE_CHECKING:
    from rdflib import Graph

DEFAULT_STALE_MINUTES = 90
STAMP_CHARS = 19  # YYYY-MM-DDTHH:MM:SS
DEFAULT_TICKS = 16
DEFAULT_OUTCOMES = ["idle"]
PROMPT = Path(".claude") / "loop-prompt.md"
SEEN = Path(".git") / "mtools" / "loop-prompt.seen"
SECONDS_PER_HOUR = 3600


def declared(text: str | None = None) -> tuple[int, list[str]]:
    """Read the declared run length and the outcomes that mean idle.

    Args:
        text: The rank-weights TOML, or None for the one that ships with the package.

    Returns:
        The number of consecutive idle ticks that triggers the warning, and the idle outcomes.

    """
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    document: dict[str, object] = tomllib.loads(text)
    table = document.get("idle")
    if not isinstance(table, dict):
        return DEFAULT_TICKS, DEFAULT_OUTCOMES
    ticks = table.get("ticks", DEFAULT_TICKS)
    outcomes = table.get("outcomes", DEFAULT_OUTCOMES)
    return (
        ticks if isinstance(ticks, int) else DEFAULT_TICKS,
        [str(o) for o in outcomes] if isinstance(outcomes, list) else DEFAULT_OUTCOMES,
    )


def idle_run(outcomes: list[str], idle: list[str]) -> int:
    """Count the trailing ticks whose outcome means idle.

    Args:
        outcomes: A repo's tick outcomes, oldest first.
        idle: The outcomes that mean nothing advanced.

    Returns:
        How many of the newest outcomes in a row are idle.

    """
    run = 0
    for outcome in reversed(outcomes):
        if outcome not in idle:
            break
        run += 1
    return run


def workable(merged: Graph, repo: str) -> int:
    """Count a repo's ready and working cards.

    Args:
        merged: The merged queue graph.
        repo: The repo.

    Returns:
        How many of its cards are ready or working.

    """
    prefix = f"{BASE}{repo}/"
    count = 0
    for state in (NEMIK.Ready, NEMIK.Working):
        count += sum(
            1
            for node in merged.subjects(OSLC_CM.state, state)
            if str(node).startswith(prefix)
        )
    return count


def prompt_lag(root: Path, repos: list[str], now: float) -> dict[str, str]:
    """Name each repo whose last acknowledged loop prompt differs from the current one (nemik:W676).

    A repo with no `loop-prompt.seen` has not ticked since mtools began recording it, and a repo
    whose git directory is a worktree's pointer file keeps its record elsewhere; neither is named,
    since a notice about something that cannot be read would train the reader to skip notices. A
    fleet with no canonical prompt names nothing.

    Args:
        root: The directory holding the repos; the prompt is `<root>/.claude/loop-prompt.md`.
        repos: The repos with a queue.
        now: The current time in epoch seconds, for the prompt's age.

    Returns:
        The warning text per lagging repo, naming how long ago the prompt changed.

    """
    prompt = root / PROMPT
    if not prompt.is_file():
        return {}
    current = prompt.read_text(encoding="utf-8")
    hours = int((now - prompt.stat().st_mtime) // SECONDS_PER_HOUR)
    found: dict[str, str] = {}
    for repo in repos:
        seen = root / repo / SEEN
        if seen.is_file() and seen.read_text(encoding="utf-8") != current:
            found[repo] = (
                f"has not acknowledged the loop prompt, which changed {hours} h ago: run "
                "--tick-open, read the changed lines, then --prompt-ack"
            )
    return found


def agent_blockers(merged: Graph, repo: str) -> list[str]:
    """Name what a repo's agent-blocked cards wait on (nemik:W577, github-8f 2026-10-27).

    amr-skills disarmed its loop on the idle warning while both its open cards waited on agents;
    the loop prompt disarms only when nothing is blocked on an agent, and nudges otherwise.

    Args:
        merged: The merged queue graph.
        repo: The repo.

    Returns:
        The distinct things its blocked cards of kind agent wait on, sorted; empty when none is
        blocked on an agent.

    """
    prefix = f"{BASE}{repo}/"
    return sorted(
        {
            str(who)
            for node in merged.subjects(OSLC_CM.state, NEMIK.Blocked)
            if str(node).startswith(prefix)
            and str(merged.value(node, NEMIK.blockedKind)) == "agent"
            for who in merged.objects(node, NEMIK.blockedOn)
        }
    )


def declared_stale_minutes(text: str) -> int:
    """Read the declared age, in minutes, past which a live loop's newest tick line is stale.

    Args:
        text: The rank-weights TOML; the caller reads the one that ships with the package.

    Returns:
        `tick_stale_minutes` of [idle], or the default when it is absent or not a whole number.

    """
    document: dict[str, object] = tomllib.loads(text)
    minutes = table(document.get("idle")).get(
        "tick_stale_minutes", DEFAULT_STALE_MINUTES
    )
    return minutes if isinstance(minutes, int) else DEFAULT_STALE_MINUTES


def live_repos(root: Path) -> tuple[set[str], str]:
    """Name the repos whose loop luthen's liveness export says is running, or why it cannot say.

    Reads only an exported `liveness.json` under the root (the file wake reads first): running
    luthen's own checker on every nemik-check is a subprocess. The answer is two parts, never a
    maybe: the repos with verdict `ok`, and the reason the export was not read (empty when it was).
    An empty set with an empty reason means no loop is live; an empty set WITH a reason means blind.

    Args:
        root: The directory holding the repos.

    Returns:
        (the repos with verdict `ok`, the reason the export could not be read or an empty string).

    """
    export = root / "liveness.json"
    if not export.exists():
        return set(), "there is no liveness.json under the root"
    try:
        document: object = json.loads(export.read_text(encoding="utf-8"))
    except OSError:
        return set(), "liveness.json cannot be read"
    except ValueError:
        return set(), "liveness.json is not JSON"
    repos = table(table(document).get("repos"))
    live = {
        name for name, record in repos.items() if table(record).get("verdict") == "ok"
    }
    return live, ""


def stale_findings(root: Path, repos: list[str], now: float) -> dict[str, str]:
    """Name each repo whose loop is live but whose ledger has no recent tick line (nemik:W1094).

    A session can work, commit and land with no tick open, and then none of the practice that hangs
    on a tick runs: no precommit, no G1, no landed-needs-witness check. The signal is a live loop
    (luthen's export) with a stale newest tick, not a stale tick alone: most repos are dormant on
    purpose. Silence is UNKNOWN, not clean (github-cb 2026-11-16): with no readable export every
    live loop is unjudged, so that is its own finding, not an empty answer.

    Args:
        root: The directory holding the repos.
        repos: The repos with a queue.
        now: The instant the age is read at, in seconds since the epoch.

    Returns:
        The warning text per live repo whose newest tick line is older than the declared bound; when
        the export cannot be read, one text saying tick staleness was not judged, on the host
        workstream (the root's own name) when it has a queue, else on the first repo.

    """
    live, blind = live_repos(root)
    if blind:
        host = root.resolve().name
        where = host if host in repos else (min(repos) if repos else "")
        unjudged = f"liveness export absent: tick staleness not judged ({blind})"
        return {where: unjudged} if where else {}
    minutes = declared_stale_minutes(
        files("nemik.data").joinpath("rank-weights.toml").read_text()
    )
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - minutes * 60))
    found: dict[str, str] = {}
    for repo in repos:
        path = root / repo / ".claude" / "paths-forward.ledger"
        if repo not in live or not path.exists():
            continue
        ticks = [
            stamp for stamp, kind, _symbol, _cls in ledger_rows(path) if kind == "tick"
        ]
        newest = max(ticks) if ticks else ""
        if newest[:STAMP_CHARS] < cutoff:
            since = f"since {newest}" if newest else "at all"
            found[repo] = (
                f"its loop is live but its ledger has no tick line {since} (bound {minutes} "
                "minutes): work with no tick open runs no G0, no G1 and no landed-needs-witness "
                "check; open a tick, or say why the loop is live and not ticking"
            )
    return found


def findings(root: Path, merged: Graph, repos: list[str]) -> dict[str, str]:
    """Name each repo that ticks idle for the declared run, or is behind on the loop prompt.

    Args:
        root: The directory holding the repos.
        merged: The merged queue graph.
        repos: The repos with a queue.

    Returns:
        The warning text per repo: idle while it has no workable card (nemik:W577), and behind on
        the canonical loop prompt (nemik:W676), joined when both hold.

    """
    limit, idle = declared()
    found: dict[str, str] = {}
    for repo in repos:
        path = root / repo / ".claude" / "paths-forward.ledger"
        if not path.exists() or workable(merged, repo):
            continue
        run = idle_run(tick_outcomes(path), idle)
        if run >= limit:
            waits = agent_blockers(merged, repo)
            remedy = (
                "every open card waits on an agent, so do not disarm: nudge on backoff "
                + ", ".join(waits)
                if waits
                else "disarm the loop, or block a card on what it waits for"
            )
            found[repo] = (
                f"its last {run} ticks advanced nothing and no card is ready or working "
                f"(declared run {limit}): {remedy}"
            )
    for repo, said in prompt_lag(root, repos, time.time()).items():
        found[repo] = f"{found[repo]}; and it {said}" if repo in found else said
    return found
