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

import time
import tomllib
from importlib.resources import files
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import PROV

from nemik.adapter import BASE, NEMIK, OSLC_CM, ledger_graph

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


def tick_outcomes(ledger: Graph) -> list[str]:
    """List a ledger's tick outcomes, oldest first.

    Args:
        ledger: The repo's ledger as activities (adapter.ledger_graph).

    Returns:
        The outcome of each line of kind tick, in time order.

    """
    rows = sorted(
        (
            str(ledger.value(node, PROV.startedAtTime)),
            str(ledger.value(node, NEMIK.outcome)),
        )
        for node in ledger.subjects(NEMIK.kind, None)
        if str(ledger.value(node, NEMIK.kind)) == "tick"
    )
    return [outcome for _, outcome in rows]


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
        run = idle_run(tick_outcomes(ledger_graph(repo, path)[0]), idle)
        if run >= limit:
            found[repo] = (
                f"its last {run} ticks advanced nothing and no card is ready or working "
                f"(declared run {limit}): disarm the loop, or block a card on what it waits for"
            )
    for repo, said in prompt_lag(root, repos, time.time()).items():
        found[repo] = f"{found[repo]}; and it {said}" if repo in found else said
    return found
