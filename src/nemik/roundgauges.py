# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1025: the round gauges, read from a published round file and the cards being worked.

roundfile writes the round file and the gauge lines; roundof measures how much of a working set lies
outside a round. This joins them for the server: it reads the round file (a head line {"as_of"} then
one card per line, the form luthen's egress gate keeps), takes the cards each repo is working, and
returns the Prometheus text. A repo with a round but nothing worked has drift 0; a repo worked but
absent from the round has a round of size 0 and every working card outside it.
"""

from nemik.pacepublish import epoch_seconds
from nemik.roundfile import metric_lines
from nemik.roundof import outside
from nemik.tracker import DICT, parse_tree

GAUGE_READABLE = "nemik_round_readable"


def read_round(text: str) -> tuple[str, dict[str, list[str]]]:
    """Read a round file.

    Args:
        text: The file's text.

    Returns:
        (the as_of stamp, each repo's round symbols in rank order); a line that is not a card or
        the head is skipped.

    Raises:
        ValueError: When the head line carries no as_of.

    """
    stamp = ""
    rounds: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            tree = parse_tree(line)
        except ValueError:
            continue
        if tree.kinds[tree.root] != DICT:
            continue
        at = tree.string(tree.root, "as_of")
        repo, symbol = tree.string(tree.root, "repo"), tree.string(tree.root, "symbol")
        if at and not stamp:
            stamp = at
        elif repo and symbol:
            rounds.setdefault(repo, []).append(symbol)
    if not stamp:
        message = "the round file carries no as_of"
        raise ValueError(message)
    return stamp, rounds


def gauge_lines(
    text: str, working: dict[str, list[str]], as_of_seconds: int
) -> list[str]:
    """Write the round gauges for a round file and the cards each repo is working.

    Args:
        text: The round file's text.
        working: Each repo's cards being worked, as symbols.
        as_of_seconds: When the round was drawn, unix seconds.

    Returns:
        roundfile.metric_lines over every repo in the round or being worked, repos sorted; a round
        file with no as_of is refused by read_round with ValueError.

    """
    _, rounds = read_round(text)
    stats: list[tuple[str, int, int, int]] = []
    for repo in sorted(set(rounds) | set(working)):
        taken, worked = rounds.get(repo, []), working.get(repo, [])
        stats.append((repo, len(taken), len(worked), len(outside(worked, taken))))
    return metric_lines(stats, as_of_seconds)


GAUGE_READY = "nemik_ready_cards"


def ready_lines(ready: dict[str, int]) -> list[str]:
    """Write how many cards each repo has ready, to read the round's size against (nemik:W1082).

    Args:
        ready: Each repo's count of cards in state ready.

    Returns:
        A TYPE line and one sample per repo, repos sorted; nothing when no repo has any.

    """
    if not ready:
        return []
    return [
        f"# TYPE {GAUGE_READY} gauge",
        *(f'{GAUGE_READY}{{repo="{repo}"}} {ready[repo]}' for repo in sorted(ready)),
    ]


def round_board(
    text: str,
    working: dict[str, list[str]],
    ready: dict[str, int] | None = None,
) -> list[str]:
    """Write every round gauge, and say whether the round file could be read at all (nemik:W1025).

    Same lesson as the pace board (W1051): a gauge that vanishes reads as no drift, so a missing
    or refused file publishes nemik_round_readable at 0 and nothing else is guessed. The ready
    counts come from the graph, not the file, so they are published either way.

    Args:
        text: The round file's text, empty when there is none.
        working: Each repo's cards being worked, as symbols.
        ready: Each repo's count of ready cards; none when not given.

    Returns:
        The readable gauge at 1 then the round gauges, or the readable gauge at 0 alone, then
        the ready gauge.

    """
    ready = ready or {}
    try:
        seconds = epoch_seconds(read_round(text)[0])
    except ValueError:
        return [
            f"# TYPE {GAUGE_READABLE} gauge",
            f"{GAUGE_READABLE} 0",
            *ready_lines(ready),
        ]
    return [
        f"# TYPE {GAUGE_READABLE} gauge",
        f"{GAUGE_READABLE} 1",
        *gauge_lines(text, working, seconds),
        *ready_lines(ready),
    ]
