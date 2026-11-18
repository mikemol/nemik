# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2256: a dangling enables names the symbol it could not resolve."""

from typing import TYPE_CHECKING

from queue_cases import make_card, write_queue

from nemik.check import shapes
from nemik.shaclinc import shacl_results

if TYPE_CHECKING:
    from pathlib import Path

SUFFIX = (
    ", which is neither a waypoint nor residue in any workstream: "
    "fix the repo prefix or the symbol"
)


def enables_messages(root: Path, targets: list[str]) -> list[str]:
    """Validate a one-card queue that enables `targets` and keep the enables messages.

    Returns:
        The messages of every enables result, sorted.

    """
    cards = [make_card("W1", "ready", [], targets)]
    g = write_queue(root / "alpha.json", "alpha", cards)
    found = [m for rows in shacl_results(g, shapes()).values() for _, m in rows]
    return sorted(m for m in found if m.startswith("enables names"))


def test_a_dangling_enables_names_each_symbol_it_could_not_resolve(
    tmp_path: Path,
) -> None:
    """A local symbol and a foreign one that exist nowhere are each named, with the repo prefix."""
    assert enables_messages(tmp_path, ["W99", "luthen:W5"]) == [
        f"enables names alpha:W99{SUFFIX}",
        f"enables names luthen:W5{SUFFIX}",
    ]


def test_an_enables_that_resolves_is_not_reported(tmp_path: Path) -> None:
    """A card that enables a card of its own queue draws no enables result."""
    cards = [make_card("W1", "ready", [], ["W2"]), make_card("W2", "ready", [], [])]
    g = write_queue(tmp_path / "alpha.json", "alpha", cards)
    found = [m for rows in shacl_results(g, shapes()).values() for _, m in rows]
    assert not [m for m in found if m.startswith("enables names")]
