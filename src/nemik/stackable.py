# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: which ready cards can be committed together as one stack.

A stack is several commits gated once, so its entries must not share a file. Each ready card
declares a manifest of exact repo-relative files it will create or edit (nemik:W612; never a
directory or a glob). Two cards overlap when their manifests share a file. The pick is greedy in
rank order: a card joins when it overlaps neither a card already picked nor a file in flight.
Greedy is not the maximum set of disjoint cards (a maximum independent set, NP-hard), but it is
how a stack is built by hand, it keeps the highest-ranked cards, and it is linear in the manifests.
"""

import json

from rdflib import Graph

from nemik.adapter import NEMIK, waypoint_uri

WIDE = 6  # a draft from past commits alone longer than this is probably wider than the card


def manifest(g: Graph, repo: str, symbol: str) -> list[str]:
    """Read a card's declared manifest from the graph.

    Args:
        g: The merged queue graph.
        repo: The card's repo.
        symbol: The card's symbol.

    Returns:
        Its planned files, sorted; empty when it declares none.

    """
    node = waypoint_uri(repo, symbol)
    return sorted(str(path) for path in g.objects(node, NEMIK.plannedPath))


def resolve(path: str, known: set[str]) -> str | None:
    """Turn a mentioned file into a tracked repo-relative path.

    Args:
        path: A path as a card's text wrote it, perhaps just a file name.
        known: The files git tracks.

    Returns:
        The path itself when tracked, the one tracked path ending in `/<path>` when exactly one
        does, otherwise None (an untracked file cannot be proposed, only declared by hand).

    """
    if path in known:
        return path
    ends = [name for name in known if name.endswith("/" + path)]
    return ends[0] if len(ends) == 1 else None


def draft(
    g: Graph, repo: str, symbol: str, cited: list[str], known: set[str]
) -> tuple[list[str], list[str]]:
    """Draft a card's manifest from what the graph and its history already say.

    Args:
        g: The merged queue graph.
        repo: The card's repo.
        symbol: The card's symbol.
        cited: The files the commits citing the card touched.
        known: The files git tracks, which every proposed path must be.

    Returns:
        (files, sources): the proposed exact files, sorted, and which evidence named them
        (`next-step`, `touches`, `commits`). Queue files are left out: the writer owns them.

    """
    node = waypoint_uri(repo, symbol)
    named = {str(path) for path in g.objects(node, NEMIK.namesFile)}
    tags = {str(tag) for tag in g.objects(node, NEMIK.touches)}
    marked = [tag for tag in tags if tag.startswith("file:")]
    declared = {tag.removeprefix("file:").removesuffix("!w") for tag in marked}
    evidence = {"next-step": named, "touches": declared, "commits": set(cited)}
    sources = [label for label, found in evidence.items() if found]
    every = {resolve(path, known) for path in named | declared | set(cited)}
    found = {path for path in every if path is not None}
    files = sorted(path for path in found if not path.startswith(".claude/"))
    return files, sources


def propose(
    g: Graph,
    repo: str,
    ranked: list[dict[str, object]],
    cited: dict[str, list[str]],
    known: set[str],
) -> list[str]:
    """Print a drafted manifest for every ready card that declares none.

    Args:
        g: The merged queue graph.
        repo: The repo's name.
        ranked: The repo's ready cards in rank order.
        cited: The files each card's citing commits touched, by symbol.
        known: The files git tracks, which every proposed path must be.

    Returns:
        One line per undeclared card: the `--update` flags to confirm, or why there is
        nothing to propose. Nothing is written; confirming is the planning act.

    """
    out: list[str] = []
    for row in ranked:
        symbol = str(row["symbol"])
        if manifest(g, repo, symbol):
            continue
        files, sources = draft(g, repo, symbol, cited.get(symbol, []), known)
        if files:
            wide = sources == ["commits"] and len(files) > WIDE
            note = ""
            if wide:
                note = f"WIDE, {len(files)} files from past commits only: narrow it; "
            out.append(
                f"{symbol}: --manifest {' '.join(files)}  ({note}from {', '.join(sources)};"
                " add --size small|medium|large)"
            )
        else:
            out.append(f"{symbol}: nothing to propose: read its code, or atomize it")
    return out


def report(
    g: Graph,
    repo: str,
    ranked: list[dict[str, object]],
    in_flight: list[str],
    generated: frozenset[str] = frozenset(),
) -> list[str]:
    """Describe the stack the repo's ready cards can make now.

    Args:
        g: The merged queue graph.
        repo: The repo's name.
        ranked: The repo's ready cards in rank order (nemik.rank.rank rows).
        in_flight: Files already staged.
        generated: The repo's generated files (.claude/generated.json): every card that
            regenerates one would overlap every other, so they leave the overlap test and ride
            the stack's last entry.

    Returns:
        One line per planned card (STACK when it joins, WAITING when a file overlaps), the
        generated files the last entry must carry, then a total with the count of cards that
        have no manifest.

    """
    cards = [f"{repo}:{row['symbol']}" for row in ranked]
    plans = [manifest(g, repo, str(row["symbol"])) for row in ranked]
    tested = [
        [path for path in files if path not in generated] or [f"(generated) {cite}"]
        if files
        else []
        for cite, files in zip(cards, plans, strict=True)
    ]
    chosen = set(pick(cards, tested, in_flight))
    out = [
        f"{'STACK  ' if cite in chosen else 'WAITING'} {cite}  {' '.join(files)}"
        for cite, files in zip(cards, plans, strict=True)
        if files
    ]
    carried = sorted(
        {
            path
            for cite, files in zip(cards, plans, strict=True)
            if cite in chosen
            for path in files
            if path in generated
        }
    )
    if carried:
        out.append(f"last entry carries: {' '.join(carried)}")
    unplanned = sum(1 for files in plans if not files)
    out.append(
        f"{len(chosen)} stackable of {len(cards)} ready; {unplanned} have no manifest"
    )
    return out


def generated_files(text: str) -> frozenset[str]:
    """Read a repo's .claude/generated.json.

    Args:
        text: The file's text, or empty when the repo has none.

    Returns:
        The exact repo-relative paths it lists as generated; none for empty or malformed text.

    """
    if not text.strip():
        return frozenset()
    try:
        document: dict[str, list[dict[str, str]]] = json.loads(text)
        return frozenset(entry["path"] for entry in document.get("generated", []))
    except (ValueError, KeyError, TypeError, AttributeError):
        return frozenset()


def pick(
    cards: list[str], manifests: list[list[str]], in_flight: list[str]
) -> list[str]:
    """Pick the cards that can stack, most urgent first.

    Args:
        cards: The ready cards' citations, in rank order.
        manifests: Each card's planned files, parallel to `cards`; an empty manifest is a card that
            is not planned, which never stacks.
        in_flight: Files already staged or in a gate.

    Returns:
        The citations that are pairwise disjoint and disjoint from `in_flight`, in rank order.

    """
    taken = set(in_flight)
    chosen: list[str] = []
    for cite, files in zip(cards, manifests, strict=True):
        if not files or taken.intersection(files):
            continue
        chosen.append(cite)
        taken.update(files)
    return chosen
