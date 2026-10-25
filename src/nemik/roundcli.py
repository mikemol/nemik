# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1024: `nemik-rank REPO --round`, the next round of a repo printed from its ranking.

The ranking is the repo's ready cards best first; the round is the top N of them (roundof), N the
median size of the stacks the repo has landed. The landing series is the file nemik-hostroot
--landings writes; the stacks are the runs of landings that share one gate time, since one stack is
one gate run. Without that file the round is one card, from none.

nemik:W1025: round_document writes every repo's round as the round file (roundfile) others read.
"""

import sys
import time
from pathlib import Path

from nemik.landings import read_document
from nemik.roundfile import round_text
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


def _ranked(rows: list[dict[str, object]]) -> list[tuple[str, str, str]]:
    """Reduce nemik-rank's rows to (symbol, salience text, title).

    Returns:
        One tuple per row, in the order given.

    """
    return [
        (str(r["symbol"]), f"{float(str(r['salience'] or 0)):.4g}", str(r["title"]))
        for r in rows
    ]


def show_round(repo: str, rows: list[dict[str, object]], landings: Path | None) -> None:
    """Print the round of a repo from its ranking rows.

    Args:
        repo: The repo.
        rows: nemik-rank's rows for it, best first, each with symbol, salience and title.
        landings: The landing file, or None.

    """
    ranked = _ranked(rows)
    sys.stdout.write("\n".join(round_lines(repo, ranked, landings)) + "\n")


def round_document(
    by_repo: dict[str, list[dict[str, object]]], landings: Path | None, stamp: str
) -> str:
    """Write the round file for every repo that has ready cards (nemik:W1025).

    Args:
        by_repo: Each repo's nemik-rank rows, best first.
        landings: The landing file, or None.
        stamp: When the rounds were drawn, a UTC stamp.

    Returns:
        The round file's text: repos sorted, each with its top N cards, N from its landed stacks.

    """
    rounds: list[tuple[str, list[tuple[str, int, str]]]] = []
    for repo in sorted(by_repo):
        size, _ = capacity(sizes_of(repo, landings))
        ranked = [(symbol, salience) for symbol, salience, _ in _ranked(by_repo[repo])]
        rounds.append((repo, round_of(ranked, size)))
    return round_text(stamp, rounds)


def write_round_file(
    by_repo: dict[str, list[dict[str, object]]], landings: Path | None, path: Path
) -> None:
    """Write the round file whole or not at all, so a reader never sees half of it (nemik:W1025).

    Args:
        by_repo: Each repo's nemik-rank rows, best first.
        landings: The landing file, or None.
        path: Where the round file goes.

    """
    now = time.gmtime()
    stamp = (
        f"{now.tm_year:04}-{now.tm_mon:02}-{now.tm_mday:02}"
        f"T{now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}Z"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(round_document(by_repo, landings, stamp), encoding="utf-8")
    temporary.replace(path)


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
