# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W415: graph.json cut into one piece per repo plus a fleet piece, and put back together.

A change in one repo then changes that repo's piece (and the fleet piece when it moves a fleet-level
number), so a page holding `hashes.json` (W414) refetches only those (W416). The pieces are cut from
the document as published, after the withheld list is applied, so each holds only fields graph.json
may hold: the manifest's check of graph.json covers them.

A node belongs to its repo when its id is a waypoint (`urn:nemik:<repo>/...`); an edge belongs
to its source's owner. Anything else (the operator, cross-repo references, inbound and the asks)
is fleet. The fleet piece is named `_fleet` because a repo name starts alphanumeric and so cannot
collide.

nemik:W2147 (codon paydown): this module compiles under the pinned Codon. GraphDoc was a TypedDict
(`total=False`, a keyword the compiler rejects, and typing.TypedDict is a wall) and is now a plain
dict that is read through nemik.tomlview's pure `table`, `tables` and `strings`, which answer a
builtin type and an empty one for any other shape; the URN prefix comes from nemik.urnbase, not
from nemik.adapter and its walls.
"""

import operator

from nemik.tomlview import strings, table, tables
from nemik.urnbase import BASE

FLEET = "_fleet"

# One row of graph.json (a node, an edge, an inbound or operator entry); only json reads it.
Row = dict[str, object]

# graph.json, and each piece of it: keys nodes, edges, inbound, operator (lists of rows), findings,
# health and ruler (tables) and, on the fleet piece only, repos (a list of names).
GraphDoc = dict[str, object]


def _node_id(node: Row) -> str:
    """Order graph nodes by id.

    Returns:
        The node's id as text.

    """
    return str(node["id"])


def _owner(node: Row) -> str:
    return str(node["repo"]) if str(node["id"]).startswith(BASE) else FLEET


def split(doc: GraphDoc) -> dict[str, GraphDoc]:
    """{piece name: piece} for a graph document; `assemble` inverts it.

    Returns:
        The pieces by name, one per repo plus the fleet piece.

    """
    nodes = tables(doc.get("nodes"))
    owner = {str(n["id"]): _owner(n) for n in nodes}
    names = sorted(set(owner.values()) - {FLEET})
    every = [*names, FLEET]
    nodes_of: dict[str, list[Row]] = {name: [] for name in every}
    edges_of: dict[str, list[Row]] = {name: [] for name in every}
    findings_of: dict[str, dict[str, object]] = {name: {} for name in every}
    health_of: dict[str, dict[str, object]] = {name: {} for name in every}
    for node in nodes:
        nodes_of[owner[str(node["id"])]].append(node)
    for edge in tables(doc.get("edges")):
        edges_of[owner.get(str(edge["source"]), FLEET)].append(edge)
    for repo, finding in table(doc.get("findings")).items():
        findings_of[repo if repo in names else FLEET][repo] = finding
    for repo, status in table(doc.get("health")).items():
        health_of[repo if repo in names else FLEET][repo] = status
    pieces: dict[str, GraphDoc] = {}
    for name in every:
        pieces[name] = {
            "nodes": nodes_of[name],
            "edges": edges_of[name],
            "findings": findings_of[name],
            "health": health_of[name],
        }
    fleet = pieces[FLEET]
    fleet["inbound"] = tables(doc.get("inbound"))
    fleet["operator"] = tables(doc.get("operator"))
    fleet["ruler"] = table(doc.get("ruler"))
    fleet["repos"] = names
    return pieces


def assemble(pieces: dict[str, GraphDoc]) -> GraphDoc:
    """Rebuild the graph document the pieces were cut from (nodes by id, edges in order).

    Returns:
        The graph document: nodes by id, edges in order.

    """
    fleet = pieces[FLEET]
    parts = [pieces[r] for r in strings(fleet.get("repos"))] + [fleet]
    nodes = sorted((n for p in parts for n in tables(p.get("nodes"))), key=_node_id)
    edges = sorted(
        (e for p in parts for e in tables(p.get("edges"))),
        key=operator.itemgetter("source", "target", "kind"),
    )
    findings: dict[str, object] = {}
    health: dict[str, object] = {}
    for p in parts:
        findings.update(table(p.get("findings")))
        health.update(table(p.get("health")))
    return {
        "nodes": nodes,
        "edges": edges,
        "inbound": tables(fleet.get("inbound")),
        "operator": tables(fleet.get("operator")),
        "findings": dict(sorted(findings.items())),
        "health": dict(sorted(health.items())),
        "ruler": table(fleet.get("ruler")),
    }
