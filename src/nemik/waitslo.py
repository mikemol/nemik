# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W700: the age a cross-repo wait should be answered within, learned from the waits.

A target typed by hand would be a threshold nobody measured. Here it is learned: take every wait's
age and whether it was answered (a wait still open is censored: it is at least that old, and may
be far older). The answered waits alone understate the age, because a wait that is never answered
never enters them; so the target is the age at which a Kaplan-Meier estimate of the share still
waiting falls to the budget, counting the open waits as censored. When the open waits are so many
and so old that the estimate never falls that far, there is no target to state, and that is the
finding, not a gap: the answered ones were the easy part.

Plain lists and floats only: the Codon census holds this module.
"""

BUDGET = 0.1  # the share of waits allowed to outlast the target: 9 in 10 are answered within it
TOLERANCE = 1e-9  # a product of fractions that should land on the budget may miss it by rounding


def target_age(rows: list[tuple[float, bool]], budget: float) -> float:
    """Learn the age by which all but `budget` of the waits have been answered.

    Args:
        rows: Each wait as (age in days, answered). An unanswered wait's age is how long it has
            waited so far.
        budget: The share allowed to outlast the target, such as 0.1.

    Returns:
        The earliest age at which the Kaplan-Meier share still waiting is at or under `budget`;
        -1.0 when the estimate never reaches it (the open waits hold it above), and -1.0 for no
        rows.

    """
    ordered = sorted(rows)
    at_risk = len(ordered)
    still = 1.0
    seen = 0
    while seen < len(ordered):
        age = ordered[seen][0]
        answered = 0
        leaving = 0
        while seen + leaving < len(ordered) and ordered[seen + leaving][0] == age:
            if ordered[seen + leaving][1]:
                answered += 1
            leaving += 1
        if answered > 0:
            still *= 1.0 - answered / at_risk
            if still <= budget + TOLERANCE:
                return age
        at_risk -= leaving
        seen += leaving
    return -1.0


def burn(rows: list[tuple[float, bool]], target: float, budget: float) -> float:
    """Say how fast the open waits spend the error budget.

    Args:
        rows: Each wait as (age in days, answered).
        target: The age a wait should be answered within (target_age); a negative one means no
            target could be learned.
        budget: The share allowed to outlast it.

    Returns:
        The share of the open waits older than the target, divided by the budget: 1.0 spends it
        exactly, 6.0 spends it six times over; 0.0 when nothing is open; -1.0 when no target was
        learned, which is not zero spend: the open waits are what kept the target from being
        learned, so a caller must not read it as a quiet queue.

    """
    if target < 0.0:
        return -1.0
    open_ages = [age for age, answered in rows if not answered]
    if not open_ages:
        return 0.0
    late = sum(1 for age in open_ages if age > target)
    return late / len(open_ages) / budget
