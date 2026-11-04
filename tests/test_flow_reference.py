# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W250: the sparse elimination in nemik.flow equals an independent dense solve, exactly."""

from __future__ import annotations

import hashlib
from fractions import Fraction

import pytest

from nemik.flow import solve

FRONT_SHARE = 0.3


WORD_BYTES = 8
WORD_RANGE = 1 << (8 * WORD_BYTES)


class _Seeded:
    """A seeded, deterministic stream over SHA-256: the graphs repeat run to run."""

    def __init__(self, seed: int) -> None:
        """Start the stream at `seed`."""
        self.seed = seed
        self.count = 0

    def _word(self) -> int:
        self.count += 1
        digest = hashlib.sha256(f"{self.seed}:{self.count}".encode()).digest()
        return int.from_bytes(digest[:WORD_BYTES], "big")

    def random(self) -> float:
        """Draw the next float from the stream.

        Returns:
            A float in [0, 1).

        """
        return self._word() / WORD_RANGE

    def randint(self, low: int, high: int) -> int:
        """Draw an integer from `low` to `high`, both included.

        Returns:
            The integer drawn.

        """
        return low + self._word() % (high - low + 1)

    def sample(self, items: list[str], k: int) -> list[str]:
        """Draw `k` distinct items, without changing `items`.

        Returns:
            The items drawn, in the order drawn.

        """
        pool = list(items)
        return [pool.pop(self._word() % len(pool)) for _ in range(k)]


def _laplacian(
    unknown: list[str], edges: list[tuple[str, str]], source: str
) -> list[list[Fraction]]:
    """Build the augmented grounded Laplacian: one row per unknown node, the source current last.

    Returns:
        The rows, each one wider than the number of unknown nodes.

    """
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
    return rows


def _reduce(rows: list[list[Fraction]]) -> list[list[Fraction]]:
    """Gauss-Jordan reduce augmented rows to reduced echelon form, exactly over the rationals.

    Returns:
        The same rows, reduced; the last column holds the solution.

    """
    n = len(rows)
    for c in range(n):
        p = next(r for r in range(c, n) if rows[r][c] != 0)
        rows[c], rows[p] = rows[p], rows[c]
        rows[c] = [x / rows[c][c] for x in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                f = rows[r][c]
                rows[r] = [a - f * b for a, b in zip(rows[r], rows[c], strict=True)]
    return rows


def _dense(
    cone: list[str], front: set[str], edges: list[tuple[str, str]], source: str
) -> dict[str, Fraction]:
    """Gauss-Jordan over the rationals on the grounded Laplacian: the reference.

    Returns:
        For each front node, the sum of the potentials of the unknown nodes joined to it.

    """
    unknown = [n for n in cone if n not in front]
    idx = {n: i for i, n in enumerate(unknown)}
    rows = _reduce(_laplacian(unknown, edges, source))
    volt = {u: rows[i][len(unknown)] for u, i in idx.items()}
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
    """The sparse elimination equals the dense solve on random graphs."""
    rng = _Seeded(seed)
    cards = [f"c{i}" for i in range(18)]
    front = {c for c in cards if rng.random() < FRONT_SHARE}
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
