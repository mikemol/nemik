# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik-metrics: print nemik's state as Prometheus text exposition (for vmagent's import).

    nemik_waypoints{repo,state}              waypoints per OSLC state
    (ready|working|blocked|done|dropped) nemik_waypoints_minted{repo,during}      waypoints by
    mtools' minted_during (tick|interrupt);
                                             absent on waypoints minted before mtools 2e21902
    nemik_findings{repo,severity}            SHACL results per severity
    (Violation|Warning|Unreadable) nemik_prompts_total{repo,source,class}   prompts recorded by the
    global hook, where class is
                                             forecast (scheduled or operator-typed tick),
                                             interrupt (operator, peer), internal (subagent
                                             hand-backs, background notices: the session's own
                                             work returning), or unknown (a source string not in
                                             this module's own CLASS map -- a new hook source,
                                             not yet classified here)
    nemik_turns_total{repo}                  turns ended (Stop events)
    nemik_ledger_lines{repo,class,kind}      parsed ledger lines (mtools ledger.read) by effort
    class nemik_blocks_inbound{repo,claimed}       open waypoints in OTHER workstreams waiting on
    repo;
                                             claimed="false" when no waypoint of repo names them
    nemik_waiting_on{repo,state}             open waypoints elsewhere waiting on repo, by repo's
                                             liveness (asleep|idle|awake|unknown)
    nemik_pathsforward_adoption{repo,state}  1 per repo:
    declared|owner|missing|no-pyproject|unobservable nemik_ledger_unparsed{repo}
    legacy/malformed ledger lines mtools returned unparsed
    nemik_realizability_waypoints{repo,coordinate}
                                             live waypoints per realizability coordinate
                                             (none|constructible|reachable|observable|coverable),
                                             judged by mtools' policy under the pinned opa
    nemik_realizability_unjudged{repo}       1 for a repo whose queue could not be judged (no pinned
                                             opa, an unreadable queue): absent coordinates are
                                             "not checked", never "clean"

    nemik_operator_salience{repo}            flow salience the repo's needs-you operator asks hold
    back,
                                             summed (what the operator owes its work; W300)
    nemik_operator_asks{repo}                how many needs-you asks that is
    nemik_warrant_debt{repo}                 open cards claiming an operator ruling in prose, no
                                             warrant (UnwarrantedRulingShape, W597); to 0 (W607)
    nemik_repo_tier{repo}                    the repo's burn-down tier as its place in the order, 0
                                             first (rank-weights.toml [tiers], W600); no gate
    nemik_waypoint_age_seconds{repo,state,quantile}
                                             age of the open waypoints per state, from issued_at:
                                             quantile 0.5 is the median, 1 the oldest (W270)

Pushing is not nemik's job: luthen hosts the push path, which admits metric names only when
its policy entails them. This command prints, and the host decides what to import.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mikemol.pathsforward.lock import stamp
from mikemol.pathsforward.opa_eval import OpaUnavailableError
from mikemol.pathsforward.store import UnreadableStateError
from rdflib import RDF, Graph
from rdflib.namespace import DCTERMS, PROV

from nemik import cachestore, forecast, history, tiers
from nemik.adapter import BASE, NEMIK, OSLC_CM, ledger_graph
from nemik.blocks import inbound, ref
from nemik.check import (
    LEDGER,
    QUEUE,
    Finding,
    default_root,
    ready_neither,
    survey,
    workstream_files,
)
from nemik.realize import verdicts
from nemik.runlogs import unmigrated_at_source
from nemik.wake import read_liveness, roster
from nemik.workrows import open_leaf_stamps, tick_kinds, working_rows


def ready_stale_lines(root: Path, now: datetime) -> list[str]:
    """nemik:W489, github:R28: per repo, the ready cards untouched past the learned bound.

    The count `nemik-check --ready-neither` lists for each repo, as a series luthen can alert on
    (stale ready cards with the watchdog armed and no landings). The bound is learned from the
    finished small cards, so a fleet that has not finished ten yields no sample at all: an unknown
    bound is never read as a zero.

    Args:
        root: The fleet root.
        now: The instant the cards are aged against.

    Returns:
        The gauge's TYPE line and a sample for every queue-bearing repo, 0 where none is late.

    """
    stamp_now = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    bound, late = ready_neither(root, stamp_now)
    out = ["# TYPE nemik_ready_stale gauge"]
    if bound < 0:
        return out
    for repo, _ in workstream_files(root, QUEUE):
        out.append(f"nemik_ready_stale{label(repo=repo)} {len(late.get(repo, []))}")
    return out


def open_leaf_lines(root: Path, now: datetime) -> list[str]:
    """nemik:W485: per repo, how many open leaves there are and how long they have waited.

    A leaf is a card nothing waits on, so it can be worked now; a count that grows while its oldest
    age grows is a repo that picks interior cards over the leaves in front of it. The age is a
    summary-style gauge (quantile 0.5 the median, 1 the oldest), as nemik_waypoint_age_seconds is.

    Args:
        root: The fleet root.
        now: The time to age the leaves against.

    Returns:
        The nemik_open_leaves and nemik_open_leaf_age_seconds lines, one set per repo.

    """
    out = [
        "# TYPE nemik_open_leaves gauge",
        "# TYPE nemik_open_leaf_age_seconds gauge",
    ]
    for repo, ledger in workstream_files(root, LEDGER):
        queue = ledger.parent / QUEUE
        text = queue.read_text(encoding="utf-8") if queue.is_file() else ""
        ages: list[float] = []
        for issued in open_leaf_stamps(text):
            try:
                born = datetime.fromisoformat(issued)
            except ValueError:
                continue
            ages.append(max(0.0, (now - born).total_seconds()))
        out.append(f"nemik_open_leaves{label(repo=repo)} {len(ages)}")
        ages.sort()
        if ages:
            for quantile, value in (("0.5", ages[len(ages) // 2]), ("1", ages[-1])):
                tags = label(repo=repo, quantile=quantile)
                out.append(f"nemik_open_leaf_age_seconds{tags} {value:.0f}")
    return out


def working_tick_lines(root: Path) -> list[str]:
    """nemik:W485: per repo, how many ledger ticks worked a directed, a leaf and an interior card.

    The series the card asks for before W486's design: where working time goes. Counts, not shares,
    so a query divides by whatever window it likes. Each tick is classified by the queue as it
    stands now (nemik.workrows), so a card that has since gained dependants moves a past tick from
    leaf to interior; the series is a reading of today's graph over the ledger's history.

    Args:
        root: The fleet root.

    Returns:
        The nemik_working_ticks lines, one per repo and kind.

    """
    out = ["# TYPE nemik_working_ticks gauge"]
    for repo, ledger in workstream_files(root, LEDGER):
        queue = ledger.parent / QUEUE
        text = queue.read_text(encoding="utf-8") if queue.is_file() else ""
        counts = tick_kinds(working_rows(ticks(repo, ledger), text))
        out.extend(
            f"nemik_working_ticks{label(repo=repo, kind=kind)} {n}"
            for kind, n in counts.items()
        )
    return out


# nemik:W620: what builds one group of families' lines when a run asks for them
Producer = Callable[[], list[str]]
TYPE_LINE_WORDS = 3  # "# TYPE", the metric name, its kind
DAY = 86400  # seconds in the arrival window

# nemik:W531: the HELP line each family prints before its TYPE line (Prometheus text format)
HELP = {
    "nemik_waypoints": "Waypoints per repo by OSLC state.",
    "nemik_waypoints_minted": "Waypoints per repo by when mtools minted them (tick or interrupt).",
    "nemik_findings": "nemik-check results per repo by severity.",
    "nemik_waypoint_age_seconds": "Age of open waypoints from issued_at, by state and quantile.",
    "nemik_prompts_total": "Prompts recorded by the global hook, by source and effort class.",
    "nemik_turns_total": "Turns ended (Stop events) per repo.",
    "nemik_ledger_lines": "Parsed ledger lines per repo by effort class and kind.",
    "nemik_ledger_unparsed": "Legacy or malformed ledger lines mtools returned unparsed.",
    "nemik_working_ticks": "Ledger ticks per repo by card kind: directed, leaf, interior.",
    "nemik_open_leaves": "Open cards per repo that nothing waits on.",
    "nemik_open_leaf_age_seconds": "Age of the open leaves from issued_at, by quantile.",
    "nemik_blocks_inbound": "Open waypoints elsewhere waiting on this repo, claimed or not.",
    "nemik_waiting_on": "Open waypoints elsewhere waiting on this repo, by its liveness.",
    "nemik_pathsforward_adoption": "1 per repo naming how its queue writer is installed.",
    "nemik_realizability_waypoints": "Live waypoints per realizability coordinate.",
    "nemik_realizability_unjudged": "1 for a repo whose queue could not be judged.",
    "nemik_operator_salience": "Flow salience the repo's needs-you operator asks hold back.",
    "nemik_operator_asks": "Needs-you operator asks the repo has open.",
    "nemik_repo_health": "Repo health: 0 green, 1 amber, 2 red.",
    "nemik_warrant_debt": "Open cards claiming an operator ruling in prose with no warrant.",
    "nemik_repo_tier": "The repo's burn-down tier as its place in the order, 0 first.",
    "nemik_cards_arrived_24h": "Cards issued in the last 24 hours, whatever their state now.",
    "nemik_cards_completed_24h": "Cards committed as done in the last 24 hours (git history).",
    "nemik_arrival_pressure": "Cards issued over cards completed in the trailing 7 days.",
    "nemik_net_inflow_per_day": "Cards issued minus completed per day over the trailing 7 days.",
    "nemik_commits_24h": "Commits on HEAD in the last 24 hours (a push is a deploy).",
    "nemik_umbrella_forecast_days": "Days the slowest umbrella needs at the recent close rate.",
    "nemik_unforecastable_cards": "Working cards with no children, so no forecast can be made.",
    "nemik_cards_reopened_24h": "Cards that went from done back to open in the last 24 hours.",
    "nemik_manifest_drift": "Done cards whose commits touched files outside their manifest.",
    "nemik_ready_stale": "Ready cards untouched past how long 9 in 10 small cards take to finish.",
    "nemik_run_log_unmigrated": "Source run-log lines that predate the run-row shape, by stream.",
}

CLASS = {
    "tick": "forecast",
    "operator-tick": "forecast",
    "operator": "interrupt",
    "peer": "interrupt",
    "subagent": "internal",
    "background": "internal",
}


def spool_path() -> Path:
    """Locate the event spool.

    Returns:
        events.jsonl under $XDG_STATE_HOME (or ~/.local/state), in the nemik directory.

    """
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(state) / "nemik" / "events.jsonl"


def label(**kv: str) -> str:
    """Format a Prometheus label set.

    Returns:
        The `{key="value",...}` text for the given pairs.

    """
    return "{" + ",".join(f'{k}="{v}"' for k, v in kv.items()) + "}"


def realizability_lines(root: Path) -> list[str]:
    """One gauge row per repo and coordinate; a queue that cannot be judged is flagged, not zeroed."""
    out = ["# TYPE nemik_realizability_waypoints gauge"]
    out.append("# TYPE nemik_realizability_unjudged gauge")
    now = stamp(datetime.now(UTC))
    for repo, path in workstream_files(root, QUEUE):
        try:
            found = verdicts(repo, path, root, now)
        except (OpaUnavailableError, UnreadableStateError):
            out.append(f"nemik_realizability_unjudged{label(repo=repo)} 1")
            continue
        by_level = Counter(str(v.get("level")) for v in found)
        for level, n in sorted(by_level.items()):
            out.append(
                f"nemik_realizability_waypoints{label(repo=repo, coordinate=level)} {n}"
            )
    return out


def operator_lines(g: Graph) -> list[str]:
    """nemik:W300: per repo, the flow salience its needs-you operator asks hold back, summed, and how
    many asks that is: what the operator owes that repo's work, in nemik-rank's units.
    """
    from nemik.blocks import operator_asks, with_salience

    held: dict[str, float] = {}
    count: dict[str, int] = {}
    for ask in with_salience(g, operator_asks(g)):
        if ask["category"] != "needs-you":
            continue
        repo = str(ask["ref"]).partition(":")[0]
        held[repo] = held.get(repo, 0.0) + float(ask["salience"])
        count[repo] = count.get(repo, 0) + 1
    out = ["# TYPE nemik_operator_salience gauge", "# TYPE nemik_operator_asks gauge"]
    for repo in sorted(held):
        out.extend(
            (
                f"nemik_operator_salience{label(repo=repo)} {held[repo]:.2f}",
                f"nemik_operator_asks{label(repo=repo)} {count[repo]}",
            )
        )
    return out


def with_help(lines: list[str]) -> list[str]:
    """Put a HELP line before each family's TYPE line (nemik:W531).

    Args:
        lines: The exposition lines, TYPE lines included.

    Returns:
        The same lines with `# HELP name text` ahead of every `# TYPE name kind`; a family with no
        text in HELP is left without one, which tests/test_metrics_help.py refuses.

    """
    out: list[str] = []
    for line in lines:
        words = line.split()
        if (
            line.startswith("# TYPE")
            and len(words) >= TYPE_LINE_WORDS
            and words[2] in HELP
        ):
            out.append(f"# HELP {words[2]} {HELP[words[2]]}")
        out.append(line)
    return out


def render(lines: list[str], families: list[str] | None) -> str:
    """Join the exposition: only the named families when given, each with its HELP line.

    Args:
        lines: The exposition lines.
        families: The families to keep, or None / empty for all.

    Returns:
        The text to print.

    """
    shown = only_families(lines, families) if families else lines
    return "\n".join(with_help(shown))


def only_families(lines: list[str], names: list[str]) -> list[str]:
    """Keep the TYPE lines and samples of the named metric families (nemik:W607).

    luthen's host job registers metric families one at a time, so what it pushes must be exactly
    those; the family list lives with the producer, passed as repeated `--family NAME`.

    Args:
        lines: The exposition lines.
        names: The family names to keep.

    Returns:
        The lines of those families, in their original order.

    """

    def family(line: str) -> str:
        words = line.split()
        if line.startswith("# TYPE") and len(words) >= TYPE_LINE_WORDS:
            return words[2]
        return line.split("{", 1)[0].split(" ", 1)[0]

    return [line for line in lines if family(line) in names]


def warrant_lines(g: Graph) -> list[str]:
    """nemik:W607: per repo, the open cards that claim an operator ruling and have no warrant.

    The warrant debt (nemik:W597's UnwarrantedRulingShape): a series to ratchet down to zero as
    the rulings gain transcript records. Every repo with a queue is listed, so zero is a value,
    not an absent series.

    Args:
        g: The merged queue graph.

    Returns:
        The gauge's TYPE line and one sample per repo.

    """
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    claims = g.subjects(NEMIK.claimsRuling, None)
    debt = Counter(ref(n).partition(":")[0] for n in claims)
    out = ["# TYPE nemik_warrant_debt gauge"]
    out += [f"nemik_warrant_debt{label(repo=repo)} {debt[repo]}" for repo in repos]
    return out


def tier_lines(g: Graph) -> list[str]:
    """nemik:W600: each repo's burn-down tier as a gauge: its position in the order, 0 first.

    Args:
        g: The merged queue graph.

    Returns:
        The gauge's TYPE line and one sample per repo. The tier is the value, not a label, so a
        tier change leaves no stale series (luthen-observability's cardinality caveat).

    """
    declared = tiers.load()
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    out = ["# TYPE nemik_repo_tier gauge"]
    for repo in repos:
        tier = declared.get(repo, tiers.UNLISTED)
        out.append(f"nemik_repo_tier{label(repo=repo)} {tiers.rank(tier)}")
    return out


def arrival_lines(g: Graph, now: datetime) -> list[str]:
    """nemik:W609: per repo, the cards issued in the last 24 hours, whatever their state now.

    Args:
        g: The merged queue graph.
        now: The instant the window ends at.

    Returns:
        The gauge's TYPE line and one sample per repo with a queue, zero included.

    """
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    fresh = arrivals_within(g, now, DAY)
    out = ["# TYPE nemik_cards_arrived_24h gauge"]
    out += [
        f"nemik_cards_arrived_24h{label(repo=repo)} {fresh[repo]}" for repo in repos
    ]
    return out


def arrivals_within(g: Graph, now: datetime, window: int) -> Counter[str]:
    """Count the cards issued within a window ending now, per repo, whatever their state now.

    Args:
        g: The merged queue graph.
        now: The instant the window ends at.
        window: The window's length in seconds.

    Returns:
        repo -> cards whose `created` falls in the window (a stamp with no zone is left out).

    """
    fresh: Counter[str] = Counter()
    for node, _, created in g.triples((None, DCTERMS.created, None)):
        try:
            born = datetime.fromisoformat(str(created))
        except ValueError:
            continue
        if born.tzinfo is not None and 0 <= (now - born).total_seconds() < window:
            fresh[ref(node).partition(":")[0]] += 1
    return fresh


def flow_sample(arrived: int, completed: int, days: int) -> tuple[float | None, float]:
    """Compare a repo's arrivals with its completions over the same trailing window.

    Both counts cover the same `days`, so a burst of minting in one window is set against the
    completions of that same window and not against a longer mean (nemik:W609, github-8f).

    Args:
        arrived: Cards issued in the window.
        completed: Cards committed as done in the window.
        days: The window's length in days.

    Returns:
        (pressure, net inflow per day): pressure is arrived over completed, None when nothing
        completed (a ratio over zero is absent, not zero); net inflow is arrived minus completed per
        day, which keeps the scale a ratio hides (2 over 1 and 200 over 100 read the same).

    """
    pressure = arrived / completed if completed else None
    return pressure, (arrived - completed) / days


def completed_in(repo_dir: Path, since: str) -> int | None:
    """Count the cards committed as done since a point in time (nemik:W609).

    Args:
        repo_dir: The repo's working directory.
        since: A zoned instant such as `2026-10-13T13:07:05+00:00` (see nemik.history.resolve,
            which refuses one with no zone).

    Returns:
        How many cards the committed queue closed between `since` and HEAD, or None when the
        directory has no committed queue (an export layout has no git history).

    """
    now: history.QueueDoc = history.queue_at(repo_dir, "HEAD")
    if not now:
        return None
    start = history.resolve(repo_dir, since)
    before: history.QueueDoc = history.queue_at(repo_dir, start)
    return len(history.diff(before, now).closed)


def completed_lines(root: Path, now: datetime) -> list[str]:
    """nemik:W609: per repo, the cards committed as done in the last 24 hours.

    Args:
        root: The fleet root.
        now: The instant the window ends at.

    Returns:
        The gauge's TYPE line and a sample for each repo whose git history is readable.

    """
    since = (now - timedelta(days=1)).astimezone().isoformat(timespec="seconds")
    out = ["# TYPE nemik_cards_completed_24h gauge"]
    for repo, path in workstream_files(root, QUEUE):
        top = path.parents[1] if path.parent.name == ".claude" else path.parent
        done = completed_in(top, since)
        if done is not None:
            out.append(f"nemik_cards_completed_24h{label(repo=repo)} {done}")
    return out


FLOW_DAYS = 7  # the trailing window the arrival-pressure gauges compare over


def flow_lines(root: Path, merged: Graph, now: datetime) -> list[str]:
    """nemik:W609: per repo, arrivals against completions over the same trailing 7 days.

    Two gauges, because a ratio hides scale: nemik_arrival_pressure is cards issued over cards
    completed (above 1: the repo mints faster than it closes; absent when nothing completed), and
    nemik_net_inflow_per_day is issued minus completed per day. An alert on either is a
    learned-baseline rule over the gauge, never a typed threshold; this only publishes them.

    Args:
        root: The fleet root.
        merged: The merged queue graph (arrivals are read from the cards' creation times).
        now: The instant the window ends at.

    Returns:
        The two gauges' TYPE lines and a sample for each repo whose git history is readable.

    """
    arrived = arrivals_within(merged, now, FLOW_DAYS * DAY)
    since = (now - timedelta(days=FLOW_DAYS)).astimezone().isoformat(timespec="seconds")
    out = [
        "# TYPE nemik_arrival_pressure gauge",
        "# TYPE nemik_net_inflow_per_day gauge",
    ]
    for repo, path in workstream_files(root, QUEUE):
        top = path.parents[1] if path.parent.name == ".claude" else path.parent
        done = completed_in(top, since)
        if done is None:
            continue
        pressure, net = flow_sample(arrived[repo], done, FLOW_DAYS)
        if pressure is not None:
            out.append(f"nemik_arrival_pressure{label(repo=repo)} {pressure:.3f}")
        out.append(f"nemik_net_inflow_per_day{label(repo=repo)} {net:.2f}")
    return out


def commit_lines(root: Path, now: datetime) -> list[str]:
    """nemik:W355: per repo, the commits in the last 24 hours, the deploy-frequency signal.

    A push is a deploy in this fleet (nemik:push-is-deploy), so commit frequency is the first DORA
    signal; change failure and time to restore need the reopened-card and Flux-ship series.

    Args:
        root: The fleet root.
        now: The instant the window ends at.

    Returns:
        The gauge's TYPE line and a sample for each repo whose git history is readable.

    """
    since = (now - timedelta(days=1)).astimezone().isoformat(timespec="seconds")
    out = ["# TYPE nemik_commits_24h gauge"]
    for repo, path in workstream_files(root, QUEUE):
        top = path.parents[1] if path.parent.name == ".claude" else path.parent
        count = history.commits_since(top, since)
        if count is not None:
            out.append(f"nemik_commits_24h{label(repo=repo)} {count}")
    return out


def reopened_lines(root: Path, now: datetime) -> list[str]:
    """nemik:W355: per repo, the cards reopened in the last 24 hours, the change-failure signal.

    Args:
        root: The fleet root.
        now: The instant the window ends at.

    Returns:
        The gauge's TYPE line and a sample for each repo whose queue history is readable.

    """
    since = (now - timedelta(days=1)).astimezone().isoformat(timespec="seconds")
    out = ["# TYPE nemik_cards_reopened_24h gauge"]
    for repo, path in workstream_files(root, QUEUE):
        top = path.parents[1] if path.parent.name == ".claude" else path.parent
        count = history.reopened_since(top, since)
        if count is not None:
            out.append(f"nemik_cards_reopened_24h{label(repo=repo)} {count}")
    return out


def ticks(repo: str, ledger: Path) -> list[tuple[str, str]]:
    """nemik:W681: the ledger's tick lines that name a card, as (stamp, symbol).

    Args:
        repo: The workstream.
        ledger: Its ledger file.

    Returns:
        One pair per line of kind `tick` that carries a symbol, in file order.

    """
    g, _ = ledger_graph(repo, ledger)
    out: list[tuple[str, str]] = []
    for act in g.subjects(RDF.type, PROV.Activity):
        used = g.value(act, PROV.used)
        if str(g.value(act, NEMIK.kind)) == "tick" and used is not None:
            stamp = str(g.value(act, PROV.startedAtTime))
            out.append((stamp, str(used).rpartition("/")[2]))
    return out


def drift_lines(root: Path, merged: Graph) -> list[str]:
    """nemik:W611: per repo, the done cards whose commits touched files outside their manifest.

    A manifest is a lower bound; a rising count says cards are understating the files they edit.
    One git walk per done card, so it is computed only when asked for by name.

    Args:
        root: The fleet root.
        merged: The merged queue graph (a card's manifest is read from it).

    Returns:
        The gauge's TYPE line and a sample for each repo with a git history.

    """
    from nemik.stackable_cli import drifted, history_cited

    out = ["# TYPE nemik_manifest_drift gauge"]
    for repo, path in workstream_files(root, QUEUE):
        top = path.parents[1] if path.parent.name == ".claude" else path.parent
        if (top / ".git").exists():
            count = len(drifted(merged, repo, history_cited(top)))
            out.append(f"nemik_manifest_drift{label(repo=repo)} {count}")
    return out


def history_lines(
    root: Path, merged: Graph, now: datetime, wanted: list[str]
) -> list[str]:
    """Compute the git-history families, only the ones named.

    A plain run once did a git walk per repo for three families and ran past luthen's relay bound
    (2026-10-17), so these are computed when asked for by name (--family), as the host job does.

    Args:
        root: The fleet root.
        merged: The merged queue graph (the forecast reads the cards' edges).
        now: The instant the windows end at.
        wanted: The family names the caller asked for.

    Returns:
        The lines of the named history families.

    """
    out: list[str] = []
    if {"nemik_umbrella_forecast_days", "nemik_unforecastable_cards"} & set(wanted):
        out += forecast.lines(root, merged, now)
    if "nemik_cards_completed_24h" in wanted:
        out += completed_lines(root, now)
    if {"nemik_arrival_pressure", "nemik_net_inflow_per_day"} & set(wanted):
        out += flow_lines(root, merged, now)
    if "nemik_commits_24h" in wanted:
        out += commit_lines(root, now)
    if "nemik_cards_reopened_24h" in wanted:
        out += reopened_lines(root, now)
    if "nemik_manifest_drift" in wanted:
        out += drift_lines(root, merged)
    return out


def health_lines(g: Graph) -> list[str]:
    """nemik:W317: each repo's health as a gauge: 0 green, 1 amber, 2 red (nemik.health, from the
    thresholds `[health]` declares in rank-weights.toml).
    """
    from nemik.blocks import ref
    from nemik.health import STATUSES, health, thresholds

    limits = thresholds()
    repos = sorted({ref(n).partition(":")[0] for n in g.subjects(OSLC_CM.state, None)})
    out = ["# TYPE nemik_repo_health gauge"]
    for repo in repos:
        level = STATUSES.index(health(g, repo, limits).status)
        out.append(f"nemik_repo_health{label(repo=repo)} {level}")
    return out


def age_lines(repo: str, g: Graph, now: datetime) -> list[str]:
    """nemik:W270: how long the open waypoints of `repo` have existed, per OSLC state, as a
    summary-style gauge: quantile 0.5 is the median age and quantile 1 the oldest. Per-waypoint
    series would be thousands of labels, and the question ("how long has the oldest one sat") is
    the quantile. Age runs from `issued_at`; a waypoint with none is left out, not counted as new.
    """
    ages: dict[str, list[float]] = {}
    for node, _, created in g.triples((None, DCTERMS.created, None)):
        state = g.value(node, OSLC_CM.state)
        if state is None:
            continue
        try:
            born = datetime.fromisoformat(str(created))
        except ValueError:
            continue
        name = str(state).rsplit("#", 1)[-1].lower()
        if name in {"done", "dropped"}:
            continue
        ages.setdefault(name, []).append(max(0.0, (now - born).total_seconds()))
    out: list[str] = []
    for name, seen in sorted(ages.items()):
        seen.sort()
        for quantile, value in (("0.5", seen[len(seen) // 2]), ("1", seen[-1])):
            out.append(
                f"nemik_waypoint_age_seconds{label(repo=repo, state=name, quantile=quantile)}"
                f" {value:.0f}"
            )
    return out


class _Options(argparse.Namespace):
    """The parsed command line, with the one option the filter reads typed."""

    family: list[str] | None
    root: Path
    runs: Path | None
    spool: Path


def run_log_lines(directory: Path | None) -> list[str]:
    """Print how many source lines of each published run log predate the run-row shape (W565).

    Args:
        directory: The export's runs/ directory, or None when no run logs are published here.

    Returns:
        One nemik_run_log_unmigrated line per stream the directory's index.json counts; nothing
        when there is no directory or no index.

    """
    if directory is None:
        return []
    counts = unmigrated_at_source(directory)
    out = ["# TYPE nemik_run_log_unmigrated gauge"] if counts else []
    out += [
        f"nemik_run_log_unmigrated{label(stream=stream)} {n}"
        for stream, n in sorted(counts.items())
    ]
    return out


def repo_lines(
    repo: str, g: Graph | None, findings: list[Finding], now: datetime
) -> list[str]:
    """Print one queue's waypoint, minted and finding gauges.

    Args:
        repo: The queue's repo.
        g: Its graph, or None when mtools refuses the file.
        findings: Its findings.
        now: When the run started.

    Returns:
        The gauge lines.

    """
    out: list[str] = []
    states: Counter[str] = Counter()
    if g is not None:
        out += age_lines(repo, g, now)
        for _, _, st in g.triples((None, OSLC_CM.state, None)):
            states[str(st).rsplit("#", 1)[-1].lower()] += 1
        states["dropped"] = sum(1 for _ in g.subjects(RDF.type, NEMIK.Dropped))
    for name, n in sorted(states.items()):
        out.append(f"nemik_waypoints{label(repo=repo, state=name)} {n}")
    if g is not None:
        for during, n in sorted(
            Counter(str(o) for o in g.objects(None, NEMIK.mintedDuring)).items()
        ):
            out.append(f"nemik_waypoints_minted{label(repo=repo, during=during)} {n}")
    for sev, n in sorted(Counter(sev for sev, _, _ in findings).items()):
        out.append(f"nemik_findings{label(repo=repo, severity=sev)} {n}")
    return out


# nemik:W620: the families that need no queue read (the spool, the ledgers, git history that does
# not need the cards' edges, realizability and the run logs); a run naming only these skips the
# survey.
HISTORY_FAMILIES = (
    "nemik_cards_completed_24h",
    "nemik_commits_24h",
    "nemik_cards_reopened_24h",
    "nemik_arrival_pressure",
    "nemik_net_inflow_per_day",
    "nemik_umbrella_forecast_days",
    "nemik_unforecastable_cards",
    "nemik_manifest_drift",
)
REALIZABILITY = ("nemik_realizability_waypoints", "nemik_realizability_unjudged")
GRAPH_FREE = frozenset(
    {
        "nemik_prompts_total",
        "nemik_turns_total",
        "nemik_ledger_lines",
        "nemik_ledger_unparsed",
        "nemik_working_ticks",
        "nemik_open_leaves",
        "nemik_open_leaf_age_seconds",
        "nemik_run_log_unmigrated",
        "nemik_cards_completed_24h",
        "nemik_commits_24h",
        "nemik_cards_reopened_24h",
        "nemik_ready_stale",
        *REALIZABILITY,
    }
)


def inbound_lines(merged: Graph) -> list[str]:
    """Count the open waypoints elsewhere that wait on each repo, claimed or not.

    Args:
        merged: The merged queue graph.

    Returns:
        The nemik_blocks_inbound gauge's lines.

    """
    out = ["# TYPE nemik_blocks_inbound gauge"]
    inb = Counter(
        (b["blocker"], str(bool(b["claimed_by"])).lower()) for b in inbound(merged)
    )
    for (repo, claimed), n in sorted(inb.items()):
        out.append(f"nemik_blocks_inbound{label(repo=repo, claimed=claimed)} {n}")
    return out


def adoption_lines(merged: Graph) -> list[str]:
    """Say how each repo's queue writer is installed.

    Args:
        merged: The merged queue graph.

    Returns:
        The nemik_pathsforward_adoption gauge's lines.

    """
    out = ["# TYPE nemik_pathsforward_adoption gauge"]
    for ws, _, state in sorted(
        merged.triples((None, NEMIK.pathsforwardAdoption, None))
    ):
        repo = str(ws).removeprefix(BASE)
        out.append(f"nemik_pathsforward_adoption{label(repo=repo, state=str(state))} 1")
    return out


def waiting_lines(root: Path, merged: Graph) -> list[str]:
    """Count the open waypoints elsewhere that wait on each repo, by the repo's liveness.

    Args:
        root: The fleet root.
        merged: The merged queue graph.

    Returns:
        The nemik_waiting_on gauge's lines.

    """
    out = ["# TYPE nemik_waiting_on gauge"]
    live, _ = read_liveness(root, None)
    out.extend(
        f"nemik_waiting_on{label(repo=r['repo'], state=r['state'])} {len(r['waiting'])}"
        for r in roster(merged, live)
    )
    return out


def spool_lines(spool: Path) -> list[str]:
    """Count the prompts and turns the global hook recorded, by repo.

    Args:
        spool: The hook's event spool; absent means no events.

    Returns:
        The nemik_prompts_total and nemik_turns_total lines.

    """
    prompts: Counter[tuple[str, str, str]] = Counter()
    turns: Counter[str] = Counter()
    if spool.exists():
        for raw in spool.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(raw)
            except json.JSONDecodeError:
                continue
            repo = e.get("repo") or "none"
            if e.get("event") == "UserPromptSubmit":
                src = e.get("source") or "unknown"
                prompts[repo, src, CLASS.get(src, "unknown")] += 1
            elif e.get("event") == "Stop":
                turns[repo] += 1
    out = ["# TYPE nemik_prompts_total counter"]
    for (repo, src, cls), n in sorted(prompts.items()):
        out.append(
            f"nemik_prompts_total{label(repo=repo, source=src, **{'class': cls})} {n}"
        )
    out.append("# TYPE nemik_turns_total counter")
    for repo, n in sorted(turns.items()):
        out.append(f"nemik_turns_total{label(repo=repo)} {n}")
    return out


def ledger_rows(root: Path) -> list[str]:
    """Count each repo's ledger lines by effort class and kind, and those that did not parse.

    Args:
        root: The fleet root.

    Returns:
        The nemik_ledger_lines and nemik_ledger_unparsed lines.

    """
    out = ["# TYPE nemik_ledger_lines gauge", "# TYPE nemik_ledger_unparsed gauge"]
    for repo, path in workstream_files(root, LEDGER):
        g, unparsed = ledger_graph(repo, path)
        lines = Counter(
            (str(c), str(k))
            for a in g.subjects(RDF.type, PROV.Activity)
            for c in g.objects(a, NEMIK.effortClass)
            for k in g.objects(a, NEMIK.kind)
        )
        for (cls, kind), n in sorted(lines.items()):
            out.append(
                f"nemik_ledger_lines{label(repo=repo, kind=kind, **{'class': cls})} {n}"
            )
        out.append(f"nemik_ledger_unparsed{label(repo=repo)} {unparsed}")
    return out


def main(argv: list[str] | None = None) -> None:
    """Print the fleet's Prometheus metrics, or only the families named with --family.

    It surveys the queues under --root, builds each asked family (a run that names only families
    that need no queue does not read the queues), keeps the flow solves in the user cache when
    --root is the real root, and prints the rendered text.

    Args:
        argv: The command line; None reads sys.argv.

    """
    ap = argparse.ArgumentParser(
        prog="nemik-metrics", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument("--spool", type=Path, default=spool_path())
    ap.add_argument(
        "--runs",
        type=Path,
        help="luthen's published run logs (DIR/index.json): print how many source lines predate "
        "the run-row shape (nemik:W565)",
    )
    ap.add_argument(
        "--family",
        action="append",
        metavar="NAME",
        help="print only this metric family (repeatable): the host job pushes the registered ones",
    )
    args = ap.parse_args(argv, namespace=_Options())

    out = [
        "# TYPE nemik_waypoints gauge",
        "# TYPE nemik_waypoints_minted gauge",
        "# TYPE nemik_findings gauge",
        "# TYPE nemik_waypoint_age_seconds gauge",
    ]
    now = datetime.now(UTC)
    asking = args.family or []

    def asked(*names: str) -> bool:
        return not asking or any(name in asking for name in names)

    # nemik:W620: a run builds only what it was asked for. The findings (SHACL and the fleet checks)
    # are most of a full run's cost and only nemik_findings reads them; the graph families need the
    # queues read, and the rest (the spool, the ledgers, the git history, realizability) need no
    # queue at all, so a run that names only those does not read the queues either.
    surveyed = (
        list(survey(args.root, check=asked("nemik_findings")))
        if not asking or not set(asking) <= GRAPH_FREE
        else []
    )
    for repo, g, findings in surveyed:
        out += repo_lines(repo, g, findings, now)

    merged = Graph()
    for _, g, _ in surveyed:
        if g is not None:
            merged += g
    steps: list[tuple[tuple[str, ...], Producer]] = [
        (("nemik_blocks_inbound",), lambda: inbound_lines(merged)),
        (("nemik_pathsforward_adoption",), lambda: adoption_lines(merged)),
        (("nemik_waiting_on",), lambda: waiting_lines(args.root, merged)),
        (
            ("nemik_operator_salience", "nemik_operator_asks"),
            lambda: operator_lines(merged),
        ),
        (("nemik_repo_health",), lambda: health_lines(merged)),
        (("nemik_warrant_debt",), lambda: warrant_lines(merged)),
        (("nemik_repo_tier",), lambda: tier_lines(merged)),
        (("nemik_cards_arrived_24h",), lambda: arrival_lines(merged, now)),
        (("nemik_run_log_unmigrated",), lambda: run_log_lines(args.runs)),
        (("nemik_ready_stale",), lambda: ready_stale_lines(args.root, now)),
        (HISTORY_FAMILIES, lambda: history_lines(args.root, merged, now, asking)),
        (REALIZABILITY, lambda: realizability_lines(args.root)),
        (("nemik_prompts_total", "nemik_turns_total"), lambda: spool_lines(args.spool)),
        (
            ("nemik_ledger_lines", "nemik_ledger_unparsed"),
            lambda: ledger_rows(args.root),
        ),
        (("nemik_working_ticks",), lambda: working_tick_lines(args.root)),
        (
            ("nemik_open_leaves", "nemik_open_leaf_age_seconds"),
            lambda: open_leaf_lines(args.root, now),
        ),
    ]
    out += [line for names, produce in steps if asked(*names) for line in produce()]
    # nemik:W640: the survey kept its caches before the families ran; keep the flow solves the
    # salience audit made since (15, 27 s of a profiled warm run), for the real root only.
    if args.root.resolve() == default_root().resolve():
        cachestore.persist_user()
    print(render(out, args.family))


if __name__ == "__main__":
    main()
