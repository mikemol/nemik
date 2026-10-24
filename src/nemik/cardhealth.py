# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W977: a repo's red, amber, green verdict over plain numbers.

nemik.health reads the numbers from rdflib-backed cards; the verdict itself needs only four of them
and the declared limits, so it lives here with no import, where the Codon census compiles it and the
browser port (nemik:W508) can run it. nemik.health stays the reference: tests/test_cardhealth.py
holds the two to the same table.
"""

STATUSES = ("green", "amber", "red")
AMBER = 1
RED = 2
INFINITY = 1e308


def share_of(blocked: int, open_cards: int) -> float:
    """Divide the blocked cards by the open cards.

    Returns:
        The blocked share, 0.0 when nothing is open.

    """
    return blocked / open_cards if open_cards else 0.0


def verdict(
    seen: list[tuple[str, float]],
    limits: dict[str, tuple[float, float]],
) -> tuple[int, list[str]]:
    """Judge the signals of one repo against the declared (amber, red) floors.

    Args:
        seen: Each signal's name and value, in the order the reasons are listed.
        limits: For each signal, its (amber, red) floor; a signal with none never crosses.

    Returns:
        (the worst level: 0 green, 1 amber, 2 red; a reason for each signal that crossed).

    """
    worst = 0
    reasons: list[str] = []
    for signal, value in seen:
        amber, red = limits.get(signal, (INFINITY, INFINITY))
        level = RED if value >= red else AMBER if value >= amber else 0
        if level:
            floor = red if level == RED else amber
            reasons.append(f"{signal} {value:g} (>= {floor:g}: {STATUSES[level]})")
        worst = max(worst, level)
    return worst, reasons
