"""Cross-repo downstream weight for ranking a queue's ready items (nemik:W34).

mtools' own ordering (mtools:W51 `model.leverage`) counts one queue's immediate edges. This module
adds the layer only nemik can see: the transitive closure across every workstream, with each
downstream waypoint weighted by `data/rank-weights.toml`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from nemik.adapter import BASE, NEMIK, OSLC_CM, workstream_uri


@dataclass(frozen=True)
class Weights:
    local: int
    peer: int
    peer_blocked: int


def load_weights(text: str | None = None) -> Weights:
    """Read the edge weights; `text` overrides the packaged file (for tests)."""
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    data = tomllib.loads(text)
    return Weights(local=int(data["local"]), peer=int(data["peer"]), peer_blocked=int(data["peer_blocked"]))


OBJECTIVES = ("operator", "band", "weight")


@dataclass(frozen=True)
class Composition:
    tiers: tuple[tuple[str, ...], ...]
    scalarize: dict[str, float]


def load_composition(text: str | None = None) -> Composition:
    """Read [order] from the weights file (nemik:W132); `text` overrides it (for tests)."""
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    o = tomllib.loads(text).get("order", {})
    tiers = tuple(tuple(t) for t in o.get("tiers", [["weight"]]))
    unknown = {x for t in tiers for x in t} - set(OBJECTIVES)
    if unknown:
        raise ValueError(f"rank-weights.toml [order]: unknown objectives {sorted(unknown)}")
    return Composition(tiers, {k: float(v) for k, v in o.get("scalarize", {}).items()})


def _dominates(a: dict, b: dict, objs: tuple[str, ...]) -> bool:
    return all(a[o] >= b[o] for o in objs) and any(a[o] > b[o] for o in objs)


def compose(rows: list[dict], comp: Composition) -> list[dict]:
    """Order rows by the declared composition; each row gets `key` (equal keys are true ties).

    Across tiers: lexicographic. Within a tier: Pareto fronts (non-dominated sorting), then the
    tier's weighted sum inside a front, then the next tier on what is still tied.
    """
    def go(items: list[dict], tiers: tuple[tuple[str, ...], ...], prefix: tuple) -> list[dict]:
        if not tiers:
            for r in items:
                r["key"] = prefix
            return sorted(items, key=lambda r: int(r["symbol"].lstrip("W")))
        objs, rest, out = tiers[0], tiers[1:], []
        remaining, front_no = list(items), 0
        while remaining:
            front = [a for a in remaining if not any(_dominates(b, a, objs) for b in remaining)]
            remaining = [a for a in remaining if a not in front]
            scal = {id(a): sum(comp.scalarize.get(o, 1.0) * a[o] for o in objs) for a in front}
            for v in sorted({scal[id(a)] for a in front}, reverse=True):
                out += go([a for a in front if scal[id(a)] == v], rest, (*prefix, front_no, -v))
            front_no += 1
        return out
    return go(list(rows), comp.tiers, ())


def objectives(g: Graph, n: URIRef, weights: Weights, bands) -> dict:
    from rdflib.namespace import PROV

    from nemik.score import band

    cause = str(g.value(n, PROV.wasInformedBy) or "").strip().lower()
    b, why = band(str(g.value(n, NEMIK.vector) or "") or None, bands)
    down = downstream_weight(g, n, weights)
    return {"operator": int(cause == "operator" or cause.startswith("operator:")),
            "band": -bands.rank(b), "band_name": b, "band_why": why, "weight": down, "downstream": down}


def _repo(node: URIRef) -> str:
    return str(node).removeprefix(BASE).partition("/")[0]


def successors(g: Graph, node: URIRef) -> set[URIRef]:
    """What this waypoint moves: what it `enables`, and every waypoint that `waitsFor` it."""
    return set(g.objects(node, NEMIK.enables)) | set(g.subjects(NEMIK.waitsFor, node))


def downstream_weight(g: Graph, node: URIRef, weights: Weights) -> int:
    """Sum of weights over the transitive downstream closure of `node`, each waypoint counted once.

    ⚑ A `done` waypoint contributes nothing and is not traversed through: finished work is not
    waiting on anything. A cycle terminates on the visited set; `node` itself never counts.
    """
    origin = _repo(node)
    seen: set[URIRef] = {node}
    stack = [node]
    total = 0
    while stack:
        for nxt in successors(g, stack.pop()):
            if nxt in seen or (nxt, OSLC_CM.state, NEMIK.Done) in g:
                continue
            seen.add(nxt)
            stack.append(nxt)
            if _repo(nxt) == origin:
                total += weights.local
            elif (nxt, OSLC_CM.state, NEMIK.Blocked) in g:
                total += weights.peer_blocked
            else:
                total += weights.peer
    return total


def _open(g: Graph, n: URIRef) -> bool:
    return (n, OSLC_CM.state, NEMIK.Done) not in g and (n, OSLC_CM.state, None) in g


def frontier(g: Graph, goal: URIRef) -> tuple[set[URIRef], set[str]]:
    """(dG, ddG) for a goal (nemik:W71, W73).

    dG: the open leaves under `goal` within its repo, found by walking back through what enables
    it and what it waits on. A leaf is an open waypoint that nothing open in the repo feeds. The
    goal is its own frontier when nothing feeds it.
    ddG: what those leaves wait on from outside the repo. That is each leaf's blocked_on entries
    that are not local symbols, plus open enablers from another repo. The path to `goal` is clear
    exactly when ddG is empty: every remaining obstacle is work this repo can do itself.
    """
    repo = _repo(goal)
    seen, stack, leaves, outside = {goal}, [goal], set(), set()
    while stack:
        n = stack.pop()
        feeders = set(g.subjects(NEMIK.enables, n)) | {
            t for t in g.objects(n, NEMIK.waitsFor) if str(t).startswith(BASE) and "/" in str(t)[len(BASE):]}
        local_open = set()
        for f in feeders:
            if not _open(g, f):
                continue
            if _repo(f) == repo:
                local_open.add(f)
            else:
                outside.add(ref_of(f))
        if not local_open:
            leaves.add(n)
            for lit in g.objects(n, NEMIK.blockedOn):
                if not re.fullmatch(r"W\d+", str(lit).strip()):
                    outside.add(str(lit))
        for f in local_open - seen:
            seen.add(f)
            stack.append(f)
    return leaves, outside


def ref_of(node: URIRef) -> str:
    r, _, sym = str(node).removeprefix(BASE).partition("/")
    return f"{r}:{sym}"


def goals(g: Graph, repo: str, weights: Weights) -> list[dict]:
    """nemik:W79 (first half of W71): `repo`'s goals, heaviest cross-repo weight first.

    A goal G is an open waypoint that nothing open in its own repo is waiting to follow: its
    purpose lies outside the repo, or it is an end in itself. For each goal: its frontier dG, the
    on-deck leaf (the heaviest ready leaf), and ddG, what the leaves wait on from outside. The path
    to G is clear exactly when ddG is empty.
    """
    ws = workstream_uri(repo)
    out = []
    for n in g.subjects(NEMIK.workstream, ws):
        if not _open(g, n):
            continue
        if any(_repo(s) == repo and _open(g, s) for s in successors(g, n)):
            continue
        leaves, outside = frontier(g, n)
        ready = sorted((x for x in leaves if (x, OSLC_CM.state, NEMIK.Ready) in g),
                       key=lambda x: (-downstream_weight(g, x, weights), str(g.value(x, NEMIK.symbol))))
        out.append({
            "goal": str(g.value(n, NEMIK.symbol)),
            "title": str(g.value(n, DCTERMS.title) or ""),
            "weight": downstream_weight(g, n, weights),
            "frontier": sorted(ref_of(x) for x in leaves),
            "on_deck": ref_of(ready[0]) if ready else None,
            "outside": sorted(outside),
            "clear": not outside,
        })
    return sorted(out, key=lambda r: (-r["weight"], int(r["goal"].lstrip("W"))))


def children(g: Graph, n: URIRef) -> set[URIRef]:
    """The open waypoints in n's own repo that directly feed it (enable it, or it waits for them)."""
    feeders = set(g.subjects(NEMIK.enables, n)) | set(g.objects(n, NEMIK.waitsFor))
    return {f for f in feeders if _repo(f) == _repo(n) and _open(g, f)}


def is_umbrella(g: Graph, n: URIRef) -> bool:
    """A ready item with open work under it (nemik:W74): its frontier is not itself, so it is not a leaf."""
    return frontier(g, n)[0] != {n}


def umbrellas(g: Graph, repo: str) -> list[URIRef]:
    ws = workstream_uri(repo)
    return [n for n in g.subjects(NEMIK.workstream, ws)
            if (n, OSLC_CM.state, NEMIK.Ready) in g and is_umbrella(g, n)]


def rank(g: Graph, repo: str, weights: Weights, comp: Composition | None = None, *, fruit_row: bool = True) -> list[dict]:
    """Every ready leaf in `repo`, in the declared composed order (nemik:W132; lower symbol on ties).

    Umbrellas are left out: their open children are what can be worked (nemik:W74).
    """
    ws = workstream_uri(repo)
    ready = [n for n in g.subjects(NEMIK.workstream, ws)
             if (n, OSLC_CM.state, NEMIK.Ready) in g and not is_umbrella(g, n)]
    from nemik.score import load_bands

    bands = load_bands()
    rows = [{"symbol": str(g.value(n, NEMIK.symbol)), "title": str(g.value(n, DCTERMS.title) or ""),
             **objectives(g, n, weights, bands)} for n in ready]
    # nemik:W178: the fruit class competes as one row. Its heaviest member stands in for it with
    # the class weight, so it is worked first exactly when the pile outweighs the deepest item.
    if fruit_row and (f := fruit(g, repo, rows, weights)) and len(f["members"]) > 1:
        rep = min((r for r in rows if r["symbol"] in f["members"]),
                  key=lambda r: (-r["downstream"], int(r["symbol"].lstrip("W"))))
        rep["weight"], rep["fruit"] = f["class_weight"], f
    out = compose(rows, comp or load_composition())
    # mtools sorts a queue by stored `weight` (--weights-from), so `weight` carries the COMPOSED
    # order: highest first, distinct unless two rows truly tie. The raw sum stays in `downstream`.
    keys = sorted({r["key"] for r in out}, reverse=True)
    for r in out:
        r["weight"] = keys.index(r["key"]) + 1
        r["key"] = list(r["key"])
    return out


FRUIT_TAG = "fruit"


def fruit(g: Graph, repo: str, rows: list[dict], weights: Weights | None = None) -> dict | None:
    """nemik:W178: the low-hanging fruit of `repo` as ONE virtual row, weighed against the rest.

    Each member counts `local` (rank-weights.toml, the weight of one waypoint in this repo) for
    the attention it costs, plus what it moves, so the class is in the same units as downstream.
    A member is a ranked ready leaf that moves nothing else (raw downstream 0) or that its repo tags
    `touches: fruit`. Each member carries the attention it costs to keep on the queue (1) plus what
    it moves; the class weighs their sum, so it outranks a deep item exactly when the pile does, and
    lightens as members land (operator 2026-10-01: no time box, the weightiest row wins).
    """
    tagged = {str(g.value(n, NEMIK.symbol)) for n in g.subjects(NEMIK.touches, Literal(FRUIT_TAG))
              if (n, NEMIK.workstream, workstream_uri(repo)) in g}
    members = [r for r in rows if r["downstream"] == 0 or r["symbol"] in tagged]
    if not members:
        return None
    return {"symbol": "FRUIT", "title": f"low-hanging fruit ({len(members)})",
            "members": [r["symbol"] for r in members],
            "class_weight": sum((weights.local if weights else 1) + r["downstream"] for r in members)}


def main(argv: list[str] | None = None, g: Graph | None = None) -> None:
    """nemik-rank REPO: REPO's ready waypoints ordered by cross-repo downstream weight."""
    import argparse
    import json
    from pathlib import Path

    from nemik.check import default_root, survey

    ap = argparse.ArgumentParser(prog="nemik-rank", description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("repo", nargs="?", default="", help="the workstream whose ready items to rank")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--goals", action="store_true",
                    help="each goal with its frontier, on-deck leaf, and outside waits (path clear iff none)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the ready item mtools works next is outweighed by another (drift witness)")
    ap.add_argument("--band", metavar="VECTOR", help="print the band a WV:1 vector falls in, and why")
    ap.add_argument("--item", metavar="REPO:W<n>", help="print the band of that waypoint, whatever its status")
    args = ap.parse_args(argv)
    if args.band:  # nemik:W152 (el-openglo:W176): check a vector's band before the item closes
        from nemik.score import band, load_bands

        b, why = band(args.band, load_bands())
        print(f"{b}  ({why})")
        raise SystemExit(1 if why.startswith("invalid") else 0)
    if g is None:
        g = Graph()
        for _, qg, _ in survey(args.root):
            if qg is not None:
                g += qg
    weights = load_weights()
    if args.item:
        from nemik.score import band, load_bands

        repo_, _, sym = args.item.partition(":")
        n = URIRef(f"{BASE}{repo_}/{sym}")
        if (n, NEMIK.symbol, None) not in g:
            print(f"rank: {args.item} is not a waypoint in any workstream")
            raise SystemExit(2)
        vec = str(g.value(n, NEMIK.vector) or "") or None
        b, why = band(vec, load_bands())
        state = str(g.value(n, OSLC_CM.state) or "").rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        print(f"{args.item}  {state}  {b}  ({why})  {vec or 'no vector'}")
        return
    if args.check:
        failed = False
        for u in umbrellas(g, args.repo):
            # nemik:W112: DECOMPOSE puts the DIRECT open children in blocked_on; the frontier is the
            # transitive leaves beneath them (paperkit read the leaves as children and found 2 of 5
            # "wrong": W59 <- W60 <- W132, W78 listed W132, W78, not W60).
            print(f"rank: UMBRELLA {ref_of(u)} is ready with open work under it: "
                  f"children {', '.join(sorted(ref_of(x) for x in children(g, u)))}; "
                  f"leaves {', '.join(sorted(ref_of(x) for x in frontier(g, u)[0]))}")
            failed = True
        rows = rank(g, args.repo, weights)
        if d := drift(g, args.repo, weights, rows):
            nxt, top = d
            print(f"rank: DRIFT {args.repo}: next is {nxt['symbol']} ({nxt['weight']}) "
                  f"but {top['symbol']} carries {top['weight']}")
            failed = True
        # nemik:W133: the declared guarantees (bands.toml), each naming the rule and the pair.
        from nemik.score import load_bands, load_guarantees

        bands = load_bands()
        guar = load_guarantees(bands=bands)
        if inv := inversion(g, args.repo, rows, bands, guar):
            nxt, top = inv
            print(f"rank: INVERSION {args.repo}: next is {nxt['symbol']} ({nxt['band_name']}) "
                  f"while {top['symbol']} is ready at {top['band_name']} (floor {guar.floor})")
            failed = True
        for dep, blocker, cls, surfaces in policy_blocks(g, args.repo, guar):
            print(f"rank: POLICY {args.repo}: {dep} is ready while {cls} {blocker} is open "
                  f"on {', '.join(surfaces)}")
            failed = True
        # A census, not a verdict (the letter's "count the unscored ones"): exit is unchanged.
        print(f"rank: UNSCORED {args.repo} {unscored(g, args.repo)}")
        if not failed:
            print(f"rank: OK {args.repo}: next ready item carries the top cross-repo weight")
        raise SystemExit(1 if failed else 0)
    if args.goals:
        gs = goals(g, args.repo, weights)
        if args.json:
            print(json.dumps(gs, indent=2))
            return
        for r in gs:
            path = "clear" if r["clear"] else "waits on " + ", ".join(r["outside"])
            print(f"{r['goal']:6} {r['weight']:4}  on deck {r['on_deck'] or '-'}; path {path}  {r['title'][:60]}")
        return
    rows = rank(g, args.repo, weights)
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print(f"{r['symbol']:6} {r['band_name']:9} op={r['operator']} down={r['downstream']:<4} {r['title'][:70]}")


def _next(g: Graph, repo: str, rows: list[dict]) -> dict:
    """The ready row mtools puts first: `nemik:queuePosition`, from `model.ordered`."""
    ws = workstream_uri(repo)
    pos = {str(g.value(n, NEMIK.symbol)): int(g.value(n, NEMIK.queuePosition))
           for n in g.subjects(NEMIK.workstream, ws) if g.value(n, NEMIK.queuePosition) is not None}
    return min(rows, key=lambda r: pos.get(r["symbol"], 1 << 30))


def drift(g: Graph, repo: str, weights: Weights, rows: list[dict] | None = None) -> tuple[dict, dict] | None:
    """(next, heavier) when the ready item mtools puts first is outweighed by another ready item.

    ⚑ "Next" is mtools' own order (`nemik:queuePosition`, from `model.ordered`), not this
    module's: the witness compares what the session WILL work against what nemik-rank says it
    should, so it fails exactly when the two disagree on the top item.
    """
    rows = rank(g, repo, weights) if rows is None else rows
    if not rows:
        return None
    nxt = _next(g, repo, rows)
    return (nxt, rows[0]) if rows[0]["weight"] > nxt["weight"] else None  # composed order (W132)


def inversion(g: Graph, repo: str, rows: list[dict], bands, guar) -> tuple[dict, dict] | None:
    """(next, urgent) when the next item sits below the declared floor band while a ready item
    at the floor or above exists (nemik:W133). `urgent` is the first such item in composed order.

    ⚑ A rule, not a weight: the composed order may itself put an item below the floor first (an
    operator ask outranks any band), and this is where that disagreement becomes visible.
    """
    if not rows or guar.floor is None:
        return None
    floor = bands.rank(guar.floor)
    nxt = _next(g, repo, rows)
    if bands.rank(nxt["band_name"]) <= floor:
        return None
    urgent = next((r for r in rows if bands.rank(r["band_name"]) <= floor), None)
    return (nxt, urgent) if urgent else None


def policy_blocks(g: Graph, repo: str, guar) -> list[tuple[str, str, str, list[str]]]:
    """(ready, blocker, class, shared surfaces) for each policy pair in `repo` (nemik:W133).

    A ready waypoint is policy-blocked by an open member of a declared class (bands.toml
    [[policy]]) when their touches share a tag other than the class's own. Members are never
    blocked by one another. Touches tags are a repo's own vocabulary, so pairs stay in one repo.
    """
    ws = workstream_uri(repo)
    nodes = [n for n in g.subjects(NEMIK.workstream, ws) if _open(g, n)]
    touches = {n: {str(t) for t in g.objects(n, NEMIK.touches)} for n in nodes}
    vector = {n: str(g.value(n, NEMIK.vector) or "") or None for n in nodes}
    sym = {n: str(g.value(n, NEMIK.symbol)) for n in nodes}
    out = []
    for p in guar.policies:
        members = {n for n in nodes if p.member(vector[n], touches[n])}
        for dep in nodes:
            if dep in members or (dep, OSLC_CM.state, NEMIK.Ready) not in g or not p.blocks(touches[dep]):
                continue
            for b in members:
                if shared := sorted((touches[dep] & touches[b]) - {p.tag}):
                    out.append((sym[dep], sym[b], p.name, shared))
    return sorted(out, key=lambda t: (int(t[0].lstrip("W")), int(t[1].lstrip("W")), t[2]))


def unscored(g: Graph, repo: str) -> int:
    """How many open waypoints in `repo` carry no vector (they rank at bands.toml `unscored`)."""
    ws = workstream_uri(repo)
    return sum(1 for n in g.subjects(NEMIK.workstream, ws)
               if _open(g, n) and g.value(n, NEMIK.vector) is None)
