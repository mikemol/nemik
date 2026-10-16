# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W593: nemik's flow cases as data, in gcalculus's flow_corpus Case shape.

A case is (name, prereq, ready, demand): `prereq` maps a node to its (prerequisite, weight) edges
(Fraction(1) where unweighted), `ready` is the frontier, `demand` the sources. The corpus holds no
expected values; the ones nemik pins are below, keyed by case name, and tests/test_flow_corpus.py
checks them against nemik.flow.solve. gcalculus appends the cases to its flow_corpus.CASES
(scripts/flow_corpus.py, commit 2193717), where flow_agree pins the dense and sparse solvers equal.
"""

from fractions import Fraction

ONE = Fraction(1)
HALF = Fraction(1, 2)

Case = tuple[str, dict[str, list[tuple[str, Fraction]]], set[str], dict[str, Fraction]]

CASES: list[Case] = [
    ("chain", {"a": [("b", ONE)], "b": [("f", ONE)]}, {"f"}, {"a": ONE}),
    (
        "chain weighted",
        {"a": [("b", Fraction(3))], "b": [("f", Fraction(1, 5))]},
        {"f"},
        {"a": ONE},
    ),
    ("parallel", {"a": [("f1", ONE), ("f2", ONE)]}, {"f1", "f2"}, {"a": ONE}),
    ("named twice", {"a": [("f", ONE), ("f", ONE)]}, {"f"}, {"a": ONE}),
    (
        "unneeded sibling",
        {"a": [("b", ONE)], "d": [("a", ONE), ("e", ONE)]},
        {"b", "e"},
        {"a": ONE},
    ),
    (
        "shared fill-in",
        {
            "z": [("y1", ONE)],
            "y1": [("s", ONE)],
            "s": [("r", ONE)],
            "y2": [("s", ONE), ("q", ONE)],
        },
        {"r", "q"},
        {"z": ONE},
    ),
    (
        "reconvergence",
        {
            "x": [("y1", ONE), ("y2", ONE)],
            "y1": [("s", ONE), ("r1", ONE)],
            "y2": [("s", ONE), ("r2", ONE)],
            "s": [("r3", ONE)],
        },
        {"r1", "r2", "r3"},
        {"x": ONE},
    ),
    (
        "both open",
        {"d": [("a", ONE), ("e", ONE)], "a": [("c", ONE)]},
        {"c", "e"},
        {"d": ONE},
    ),
    ("landed", {"d": [("e", ONE)]}, {"e"}, {"d": ONE}),
    ("outside the frontier", {"a": [("outside", ONE)]}, {"f"}, {"a": ONE}),
    (
        "two-cycle",
        {"a": [("b", ONE), ("f", ONE)], "b": [("a", ONE)]},
        {"f"},
        {"b": ONE},
    ),
    ("ready source", {}, {"f"}, {"f": HALF}),
    (
        "fibre",
        {"p": [("f", ONE)], "q": [("f", ONE)]},
        {"f"},
        {"p": ONE, "q": ONE},
    ),
]

# what nemik pins, by case name; a case absent from a table pins nothing of that kind
SALIENCE: dict[str, dict[str, Fraction]] = {
    "unneeded sibling": {"b": ONE},
    "shared fill-in": {"r": ONE},
    "reconvergence": {
        "r1": Fraction(3, 8),
        "r2": Fraction(3, 8),
        "r3": Fraction(1, 4),
    },
    "landed": {"e": ONE},
    "outside the frontier": {},
    "two-cycle": {"f": ONE},
    "ready source": {"f": HALF},
    "fibre": {"f": 2 * ONE},
}
STRANDED: dict[str, dict[str, Fraction]] = {"outside the frontier": {"a": ONE}}
FIBRE: dict[str, dict[str, Fraction]] = {"fibre": {"p": ONE, "q": ONE}}
# the conductance 1/potential of the source `a`
CONDUCTANCE: dict[str, Fraction] = {
    "chain": HALF,
    "chain weighted": Fraction(3, 16),
    "parallel": Fraction(2),
    "named twice": ONE,
}
# which ready cards get any demand, where only that is pinned
SALIENCE_KEYS: dict[str, set[str]] = {"both open": {"c", "e"}}
