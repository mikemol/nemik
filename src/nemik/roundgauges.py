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
from nemik.tracker import parse

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
        try:
            body = parse(line) if line.strip() else None
        except ValueError:
            continue
        if not isinstance(body, dict):
            continue
        at, repo, symbol = body.get("as_of"), body.get("repo"), body.get("symbol")
        if isinstance(at, str) and not stamp:
            stamp = at
        elif isinstance(repo, str) and isinstance(symbol, str):
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


def round_board(text: str, working: dict[str, list[str]]) -> list[str]:
    """Write every round gauge, and say whether the round file could be read at all (nemik:W1025).

    Same lesson as the pace board (W1051): a gauge that vanishes reads as no drift, so a missing
    or refused file publishes nemik_round_readable at 0 and nothing else is guessed.

    Args:
        text: The round file's text, empty when there is none.
        working: Each repo's cards being worked, as symbols.

    Returns:
        The readable gauge at 1 then the round gauges, or the readable gauge at 0 alone.

    """
    try:
        seconds = epoch_seconds(read_round(text)[0])
    except ValueError:
        return [f"# TYPE {GAUGE_READABLE} gauge", f"{GAUGE_READABLE} 0"]
    return [
        f"# TYPE {GAUGE_READABLE} gauge",
        f"{GAUGE_READABLE} 1",
        *gauge_lines(text, working, seconds),
    ]
