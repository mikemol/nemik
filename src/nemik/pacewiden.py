# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2042: ask the store for a short window first, and widen only the ratchets that need more.

nemik-hostroot --pace read three raw exports over a fixed 30 days, and the unit that runs it
(luthen's luthen-nemik-pace.service, bounded by 120 s of CPU) was killed at that limit on every
run, so the pace file the gate reads sat nine days stale. A busy ratchet holds all the samples
the pace reads in a few days; a quiet one needs the long window, and one quiet for days has no
sample in the short window at all, so the ratchets that exist come from the store's series list,
not from the short export.

    known_from(text)                         the (repo, ratchet) pairs of a series-list answer
    short_by_repo(text, window, known)       the ratchets short of what the pace reads, by repo
    widened_selector(selector, repo, names)  the selector narrowed to those ratchets of one repo

Plain lists, dicts and strings, no import of the store's reader, so the Codon census compiles it.
"""

from nemik.ratchetpace import MIN_WINDOWS
from nemik.ratchetseries import PHANTOM, export_series
from nemik.tracker import DICT, LIST, parse_tree

# characters that mean something in a PromQL regular expression, escaped to match themselves
REGEX_META = ".+*?()|[]{}^$\\"


def known_from(text: str) -> list[tuple[str, str]]:
    """Read the (repo, ratchet) pairs out of the store's series-list answer.

    Args:
        text: The answer, {"status": "success", "data": [{"repo": ..., "ratchet": ..., ...}]}.

    Returns:
        One pair per series that carries both labels; empty when the text is not an answer.

    """
    try:
        tree = parse_tree(text)
    except ValueError:
        return []
    if tree.kinds[tree.root] != DICT:
        return []
    data = tree.get(tree.root, "data")
    if tree.kinds[data] != LIST:
        return []
    pairs: list[tuple[str, str]] = []
    for labels in tree.kids[data]:
        if tree.kinds[labels] == DICT:
            repo, ratchet = tree.string(labels, "repo"), tree.string(labels, "ratchet")
            if repo and ratchet:
                pairs.append((repo, ratchet))
    return pairs


def short_by_repo(
    text: str, window: int, known: list[tuple[str, str]]
) -> dict[str, list[str]]:
    """Group the ratchets whose short export does not hold the samples the pace reads.

    The pace reads the last window for what a ratchet fell and several whole earlier windows for
    what it owes (ratchetpace.seed), so a ratchet needs `window` times its whole windows, not one
    window. A ratchet quiet for days has NO sample in a short export: `known` (the store's series
    list) names it, and it counts as short, or it would be missing from the file.

    Args:
        text: The short-window export's lines.
        window: How many landings the pace judges over.
        known: Every (repo, ratchet) the store holds in the long window.

    Returns:
        {repo: its ratchets with too few samples, sorted}; a repo with none is absent.

    """
    need = window * (MIN_WINDOWS + 1)
    have: dict[str, int] = {}
    for repo, ratchet, values in export_series(text):
        have[f"{repo}\n{ratchet}"] = len(values)
    short: dict[str, list[str]] = {}
    for repo, ratchet in known:
        real = bool(repo) and bool(ratchet) and repo != PHANTOM
        if real and have.get(f"{repo}\n{ratchet}", 0) <= need:
            short.setdefault(repo, []).append(ratchet)
    return {repo: sorted(set(names)) for repo, names in short.items()}


def _escaped(name: str) -> str:
    """Escape a ratchet name for a PromQL regular expression inside a double-quoted string.

    Returns:
        The name with each regex metacharacter backslashed, the backslash itself doubled for the
        string.

    """
    out = ""
    for char in name:
        if char in REGEX_META:
            out += "\\\\"
        out += char
    return out


def widened_selector(selector: str, repo: str, ratchets: list[str]) -> str:
    """Narrow a `{...}` selector to the named ratchets of one repo.

    Args:
        selector: The series selector, ending in its closing brace.
        repo: The repo whose ratchets are wanted.
        ratchets: Their names.

    Returns:
        The selector with a repo label and a regular expression over the ratchet names added.

    """
    alternatives = "|".join(_escaped(name) for name in ratchets)
    return f'{selector[:-1]},repo="{repo}",ratchet=~"{alternatives}"}}'
