# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W643: dependency cones over a repo's input graph, to group and chain cards.

The input graph is mtools' graph.json (mikemol.importdag.graph, schema 1): for each module and test,
the files it imports and the files it declares it reads. A card's cone is what its manifest files
depend on, transitively, so two cards whose cones are disjoint can be worked in parallel, and a card
that edits a file in another's cone has to land first. The graph is data: nemik reads the file and
does not import the generator.
"""

import json
from pathlib import Path

Graph = dict[str, set[str]]  # path -> the paths it imports or reads


def _deps(row: object) -> set[str]:
    """Read one module's or test's direct dependencies.

    Args:
        row: Its {imports, reads} object.

    Returns:
        The imported and read paths; empty when the row is not an object.

    """
    deps: set[str] = set()
    if isinstance(row, dict):
        for field in ("imports", "reads"):
            found: object = row.get(field)
            if isinstance(found, list):
                deps |= {str(d) for d in found}
    return deps


def load(path: Path) -> Graph:
    """Read a graph.json into path -> everything that path depends on directly.

    Args:
        path: The graph.json file.

    Returns:
        modules and tests merged, each path to its imports and reads; empty when the file is
        missing, unreadable or not a schema-1 graph, because a missing graph must not read as
        "nothing depends on anything".

    """
    try:
        doc: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except ValueError:
        return {}
    out: Graph = {}
    if not isinstance(doc, dict):
        return out
    schema: object = doc.get("schema")
    if schema != 1:
        return out
    for section in ("modules", "tests"):
        rows: object = doc.get(section)
        if not isinstance(rows, dict):
            continue
        out.update({str(name): _deps(row) for name, row in rows.items()})
    return out


def cone(files: list[str], graph: Graph) -> set[str]:
    """Collect everything the files depend on, transitively, themselves included.

    Args:
        files: A card's manifest files.
        graph: The input graph.

    Returns:
        The files and every path reachable from them; a file the graph does not know stays in the
        cone and depends on nothing.

    """
    seen: set[str] = set()
    todo = list(files)
    while todo:
        here = todo.pop()
        if here in seen:
            continue
        seen.add(here)
        todo.extend(graph.get(here, set()) - seen)
    return seen


def relation(edits_a: list[str], edits_b: list[str], graph: Graph) -> str:
    """Say how two cards must be ordered, from the files each edits.

    Args:
        edits_a: The files card A edits.
        edits_b: The files card B edits.
        graph: The input graph.

    Returns:
        "disjoint" when neither edits a file in the other's cone, so they can run in parallel;
        "a-first" when B depends on something A edits; "b-first" when A depends on something B
        edits; "both" when each does (a cycle between the cards, or one file edited by both),
        which no order settles.

    """
    a_feeds_b = bool(set(edits_a) & cone(edits_b, graph))
    b_feeds_a = bool(set(edits_b) & cone(edits_a, graph))
    if a_feeds_b and b_feeds_a:
        return "both"
    if a_feeds_b:
        return "a-first"
    if b_feeds_a:
        return "b-first"
    return "disjoint"


def parallel(
    cards: list[str], manifests: list[list[str]], in_flight: list[str], graph: Graph
) -> list[str]:
    """Pick the cards that can be worked at the same time, most urgent first.

    Where nemik.stackable.pick asks for disjoint file lists, this asks for disjoint cones: a card
    whose edits feed what another depends on is not parallel with it, even on different files.

    Args:
        cards: The ready cards' citations, in rank order.
        manifests: Each card's planned files, parallel to `cards`; an empty manifest is a card that
            is not planned, which is never picked.
        in_flight: Files already staged or in a gate.
        graph: The input graph.

    Returns:
        The citations whose cones are pairwise disjoint from each other and from `in_flight`, in
        rank order.

    """
    taken = list(in_flight)
    chosen: list[str] = []
    for cite, files in zip(cards, manifests, strict=True):
        if not files or relation(taken, files, graph) != "disjoint":
            continue
        chosen.append(cite)
        taken.extend(files)
    return chosen
