# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W611: how far a landed commit's files strayed from its card's manifest.

A manifest is a lower bound: mtools' first manifested stack found a file the manifest missed
(ratchet/mutants.regex) and two cards understated badly (a new mode plus tests and warrants). The
drift of a card is the files its commits touched that its manifest did not name. The files that
keep riding along (tests, warrants, BUILD files) become suggested additions to the next draft.
"""

DIRECTORY = "/"


def drift(touched: list[str], manifest: list[str]) -> list[str]:
    """List the files a card's commits touched that its manifest did not name.

    Args:
        touched: The files the commits citing the card changed.
        manifest: The files the card declared. An entry ending in / names a directory.

    Returns:
        The touched files outside the manifest, sorted and without repeats.

    """
    declared = set(manifest)
    folders = [m for m in manifest if m.endswith(DIRECTORY)]
    out: set[str] = set()
    for path in touched:
        if path in declared:
            continue
        if any(path.startswith(folder) for folder in folders):
            continue
        out.add(path)
    return sorted(out)


def kind(path: str) -> str:
    """Classify a file by how it rides along with another.

    Args:
        path: A repo-relative path.

    Returns:
        Its directory with a trailing slash when it has one (tests/, .claude/), otherwise its
        basename (BUILD.bazel, pyproject.toml).

    """
    head, _, tail = path.rpartition(DIRECTORY)
    return head + DIRECTORY if head else tail


def ride_along(drifts: list[list[str]], at_least: int) -> list[tuple[str, int]]:
    """Find the kinds of file that keep missing from manifests.

    Args:
        drifts: One drift per card, as drift() returns it.
        at_least: How many cards must have missed a kind before it is reported.

    Returns:
        (kind, cards that missed it) for each kind at or above the bar, most common first, ties
        in kind order.

    """
    counts: dict[str, int] = {}
    for card in drifts:
        for one in {kind(path) for path in card}:
            counts[one] = counts.get(one, 0) + 1
    rows = [(name, n) for name, n in counts.items() if n >= at_least]
    return sorted(rows, key=_by_count)


def _by_count(row: tuple[str, int]) -> tuple[int, str]:
    """Order ride-along rows.

    Args:
        row: A (kind, cards) row.

    Returns:
        Most cards first, then name.

    """
    return (-row[1], row[0])
