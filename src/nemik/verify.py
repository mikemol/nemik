# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W748: verification, how far a forecast's chances were from what happened.

A forecast (nemik:W747) says "P(done by +3d) = 0.4"; the truth is whether the card was done. The
Brier score is the mean squared distance between the chances and the outcomes (0 is perfect, 0.25 is
what saying 0.5 every time earns, 1 is certainty wrong every time). A forecast is only scored at a
lead no finer than the grain of the truth it is scored against (operator ruling, record 8f3e501d:
backfilled history is commit-grain, so a lead shorter than the gap between commits would be scored
against noise). No import, no future import: compiles under Codon as written.
"""


def brier(pairs: list[tuple[float, bool]]) -> float:
    """Score forecasts by the mean squared error of their chances.

    Args:
        pairs: Each forecast's chance of "done" and whether the card was done.

    Returns:
        The Brier score from 0.0 to 1.0, lower better; 0.0 for no forecasts.

    """
    if not pairs:
        return 0.0
    return sum((chance - (1.0 if done else 0.0)) ** 2 for chance, done in pairs) / len(
        pairs
    )


def scorable(lead_days: float, grain_days: float) -> bool:
    """Say whether a lead is coarse enough to score against truth of this grain.

    A lead shorter than the grain of the observations would be judged against noise: the moment
    a card finished is not known more finely than the gap between the commits that saw it.

    Returns:
        True when the lead is at least the grain.

    """
    return lead_days >= grain_days
