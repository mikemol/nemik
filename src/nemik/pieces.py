"""nemik:W415: graph.json cut into one piece per repo plus a fleet piece, and put back together.

A change in one repo then changes that repo's piece (and the fleet piece when it moves a fleet-level
number), so a page holding `hashes.json` (W414) refetches only those (W416). The pieces are cut from
the document as published, after the withheld list is applied, so each holds only fields graph.json
may hold: the manifest's check of graph.json covers them.

A node belongs to its repo when its id is a waypoint (`urn:nemik:<repo>/...`); an edge belongs to its
source's owner. Anything else (the operator, cross-repo references, inbound and the asks) is fleet.
The fleet piece is named `_fleet` because a repo name starts alphanumeric and so cannot collide.
"""

from __future__ import annotations

from typing import Any

from nemik.adapter import BASE

FLEET = "_fleet"


def _owner(node: dict[str, Any]) -> str:
    return str(node["repo"]) if str(node["id"]).startswith(BASE) else FLEET


def split(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """{piece name: piece} for a graph document; `assemble` inverts it."""
    owner = {str(n["id"]): _owner(n) for n in doc["nodes"]}
    names = sorted(set(owner.values()) - {FLEET})
    pieces: dict[str, dict[str, Any]] = {
        name: {"nodes": [], "edges": [], "findings": {}, "health": {}}
        for name in [*names, FLEET]
    }
    for node in doc["nodes"]:
        pieces[owner[str(node["id"])]]["nodes"].append(node)
    for edge in doc["edges"]:
        pieces[owner.get(str(edge["source"]), FLEET)]["edges"].append(edge)
    for section in ("findings", "health"):
        for repo, value in doc.get(section, {}).items():
            pieces[repo if repo in names else FLEET][section][repo] = value
    fleet = pieces[FLEET]
    fleet["inbound"] = doc.get("inbound", [])
    fleet["operator"] = doc.get("operator", [])
    fleet["repos"] = names
    return pieces


def assemble(pieces: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The graph document the pieces were cut from (nodes by id, edges in the published order)."""
    fleet = pieces[FLEET]
    parts = [pieces[r] for r in fleet["repos"]] + [fleet]
    nodes = sorted((n for p in parts for n in p["nodes"]), key=lambda n: str(n["id"]))
    edges = sorted(
        (e for p in parts for e in p["edges"]),
        key=lambda e: (e["source"], e["target"], e["kind"]),
    )
    doc: dict[str, Any] = {
        "nodes": nodes,
        "edges": edges,
        "inbound": fleet["inbound"],
        "operator": fleet["operator"],
        "findings": {},
        "health": {},
    }
    for section in ("findings", "health"):
        for p in parts:
            doc[section].update(p[section])
        doc[section] = dict(sorted(doc[section].items()))
    return doc
