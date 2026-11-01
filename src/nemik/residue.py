# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W251: every recorded gap in the fleet, by card, for the flow model's residue demand.

The policy (mtools:W850) judges each live waypoint and returns its residue: the gaps it has not
closed, per gate. This keys those entries by `repo:W<n>`, so `nemik.salience.audit` can inject
demand at the cards that bear them. Judging the queues is `nemik.metrics.judged_cards`, so this
module needs no import and is a pure function of the verdicts it is given.

An opa that is absent raises where the judging happens (`nemik.realize.verdicts`): a card that was
not judged has no residue recorded, and that must never read as a card with none.
"""


def by_card(judged: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """Collect each judged card's residue entries.

    Args:
        judged: One verdict per judged card, each {ref, level, reference_arm, residue}.

    Returns:
        `repo:W<n>` to its residue entries, for every card that has any.

    """
    out: dict[str, list[dict[str, object]]] = {}
    for verdict in judged:
        entries = verdict.get("residue")
        if isinstance(entries, list) and entries:
            out[str(verdict.get("ref"))] = [e for e in entries if isinstance(e, dict)]
    return out
