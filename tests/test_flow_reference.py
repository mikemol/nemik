"""nemik:W250: the sparse elimination in nemik.flow equals an independent dense solve, exactly."""

from __future__ import annotations

import random
from fractions import Fraction

import pytest

from nemik.flow import solve


def _dense(
    cone: list[str], front: set[str], edges: list[tuple[str, str]], source: str
) -> dict[str, Fraction]:
    """Gauss-Jordan over the rationals on the grounded Laplacian: the reference."""
    unknown = [n for n in cone if n not in front]
    idx = {n: i for i, n in enumerate(unknown)}
    n = len(unknown)
    rows = [[Fraction(0)] * (n + 1) for _ in range(n)]
    for u, v in edges:
        for a, b in ((u, v), (v, u)):
            if a in idx:
                rows[idx[a]][idx[a]] += 1
                if b in idx:
                    rows[idx[a]][idx[b]] -= 1
    rows[idx[source]][n] = Fraction(1)
    for c in range(n):
        p = next(r for r in range(c, n) if rows[r][c] != 0)
        rows[c], rows[p] = rows[p], rows[c]
        rows[c] = [x / rows[c][c] for x in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                f = rows[r][c]
                rows[r] = [a - f * b for a, b in zip(rows[r], rows[c], strict=True)]
    volt = {u: rows[i][n] for u, i in idx.items()}
    into: dict[str, Fraction] = {}
    for u, v in edges:
        for a, b in ((u, v), (v, u)):
            if b in front and a in volt:
                into[b] = into.get(b, Fraction(0)) + volt[a]
    return into


def _cone(needs: dict[str, list[str]], front: set[str], source: str) -> list[str]:
    seen: set[str] = set()
    stack = [source]
    while stack:
        c = stack.pop()
        if c not in seen:
            seen.add(c)
            if c not in front:
                stack.extend(needs.get(c, []))
    return sorted(seen)


@pytest.mark.parametrize("seed", range(12))
def test_the_sparse_elimination_equals_the_dense_solve_on_random_graphs(
    seed: int,
) -> None:
    rng = random.Random(seed)
    cards = [f"c{i}" for i in range(18)]
    front = {c for c in cards if rng.random() < 0.3}
    # Edges point from a later card to an earlier one, plus a few back edges (cycles).
    needs: dict[str, list[str]] = {}
    for i, c in enumerate(cards):
        if c in front or i == 0:
            continue
        picks = rng.sample(cards[:i], k=min(i, rng.randint(1, 3)))
        needs[c] = sorted(set(picks))
    for _ in range(2):
        a, b = rng.sample(cards, 2)
        if a not in front:
            needs[a] = sorted(set(needs.get(a, [])) | {b})
    demand = {
        c: Fraction(rng.randint(1, 5)) for c in cards if c not in front and c in needs
    }
    flow = solve(demand, needs, front)
    for source, amount in demand.items():
        cone = _cone(needs, front, source)
        if not any(n in front for n in cone):
            assert flow.stranded[source] == amount
            continue
        edges = sorted(
            {(u, p) for u in cone if u not in front for p in needs.get(u, [])}
        )
        want = _dense(cone, front, edges, source)
        for card, current in want.items():
            assert flow.fibre[card][source] == current * amount
