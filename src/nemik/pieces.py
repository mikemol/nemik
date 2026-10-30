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
"""

from __future__ import annotations

import operator
from typing import TypedDict

from nemik.adapter import BASE

FLEET = "_fleet"

# One row of graph.json (a node, an edge, an inbound or operator entry); only json reads it.
Row = dict[str, object]


class GraphDoc(TypedDict, total=False):
    """graph.json, and each piece of it (a piece adds `repos` on the fleet piece only)."""

    nodes: list[Row]
    edges: list[Row]
    inbound: list[Row]
    operator: list[Row]
    findings: dict[str, object]
    health: dict[str, object]
    ruler: dict[str, object]
    repos: list[str]


def _owner(node: Row) -> str:
    return str(node["repo"]) if str(node["id"]).startswith(BASE) else FLEET


def split(doc: GraphDoc) -> dict[str, GraphDoc]:
    """{piece name: piece} for a graph document; `assemble` inverts it.

    Returns:
        The pieces by name, one per repo plus the fleet piece.

    """
    owner = {str(n["id"]): _owner(n) for n in doc["nodes"]}
    names = sorted(set(owner.values()) - {FLEET})
    pieces: dict[str, GraphDoc] = {
        name: {"nodes": [], "edges": [], "findings": {}, "health": {}}
        for name in [*names, FLEET]
    }
    for node in doc["nodes"]:
        pieces[owner[str(node["id"])]]["nodes"].append(node)
    for edge in doc["edges"]:
        pieces[owner.get(str(edge["source"]), FLEET)]["edges"].append(edge)
    for repo, finding in doc.get("findings", {}).items():
        pieces[repo if repo in names else FLEET]["findings"][repo] = finding
    for repo, status in doc.get("health", {}).items():
        pieces[repo if repo in names else FLEET]["health"][repo] = status
    fleet = pieces[FLEET]
    fleet["inbound"] = doc.get("inbound", [])
    fleet["operator"] = doc.get("operator", [])
    fleet["ruler"] = doc.get("ruler", {})
    fleet["repos"] = names
    return pieces


def assemble(pieces: dict[str, GraphDoc]) -> GraphDoc:
    """Rebuild the graph document the pieces were cut from (nodes by id, edges in order).

    Returns:
        The graph document: nodes by id, edges in order.

    """
    fleet = pieces[FLEET]
    parts = [pieces[r] for r in fleet["repos"]] + [fleet]
    nodes = sorted((n for p in parts for n in p["nodes"]), key=lambda n: str(n["id"]))
    edges = sorted(
        (e for p in parts for e in p["edges"]),
        key=operator.itemgetter("source", "target", "kind"),
    )
    findings: dict[str, object] = {}
    health: dict[str, object] = {}
    for p in parts:
        findings.update(p["findings"])
        health.update(p["health"])
    return {
        "nodes": nodes,
        "edges": edges,
        "inbound": fleet["inbound"],
        "operator": fleet["operator"],
        "findings": dict(sorted(findings.items())),
        "health": dict(sorted(health.items())),
        "ruler": fleet["ruler"],
    }
