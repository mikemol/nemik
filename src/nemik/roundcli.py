# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: `nemik-rank REPO --round`, the next round of a repo printed from its ranking.

The ranking is the repo's ready cards best first; the round is the top N of them (roundof), N the
median size of the stacks the repo has landed. The landing series is the file nemik-hostroot
--landings writes; the stacks are the runs of landings that share one gate time, since one stack is
one gate run. Without that file the round is one card, from none.
"""

import sys
from pathlib import Path

from nemik.landings import read_document
from nemik.roundof import capacity, round_of, stack_sizes

RECENT = 10  # landed stacks the capacity looks back over


def sizes_of(repo: str, landings: Path | None) -> list[int]:
    """Read a repo's recent landed-stack sizes from the landing file.

    Args:
        repo: The repo whose landings are read.
        landings: The landing file, or None when there is none.

    Returns:
        The sizes of its last RECENT stacks, oldest first; empty without a readable file.

    """
    if landings is None:
        return []
    try:
        _, rows = read_document(landings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    mine = [str(row.gate_s) for row in rows if row.repo == repo]
    return stack_sizes(mine)[-RECENT:]


def show_round(repo: str, rows: list[dict[str, object]], landings: Path | None) -> None:
    """Print the round of a repo from its ranking rows.

    Args:
        repo: The repo.
        rows: nemik-rank's rows for it, best first, each with symbol, salience and title.
        landings: The landing file, or None.

    """
    ranked = [
        (str(r["symbol"]), f"{float(str(r['salience'] or 0)):.4g}", str(r["title"]))
        for r in rows
    ]
    sys.stdout.write("\n".join(round_lines(repo, ranked, landings)) + "\n")


def round_lines(
    repo: str, ranked: list[tuple[str, str, str]], landings: Path | None
) -> list[str]:
    """Print the round of a repo.

    Args:
        repo: The repo.
        ranked: Its ready cards best first, each as (symbol, salience text, title).
        landings: The landing file, or None.

    Returns:
        A header naming the round size and where it came from, then one line per card of the round.

    """
    size, source = capacity(sizes_of(repo, landings))
    taken = round_of([(symbol, salience) for symbol, salience, _ in ranked], size)
    titles = {symbol: title for symbol, _, title in ranked}
    head = f"round {repo}: {len(taken)} of {len(ranked)} ready cards (size {size}, from {source})"
    return [
        head,
        *(
            f"{place:3} {symbol:6} salience {salience:>8}  {titles[symbol][:60]}"
            for symbol, place, salience in taken
        ),
    ]
