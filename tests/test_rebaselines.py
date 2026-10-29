# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1046: a declared re-baseline restarts a ratchet's history; no other fall is hidden."""

from nemik.ratchetpace import verdict
from nemik.rebaselines import DECLARED, Declared, since

STEP: list[Declared] = [("a", "x.json", 264, 168, "lists only failing entries")]
FALL = [270, 266, 264, 168, 168, 167]
WINDOW = 3


def test_history_starts_at_the_declared_step() -> None:
    """The 264 to 168 step is the new start: the drop is not in the history."""
    assert since(FALL, "a", "x.json", STEP) == [168, 168, 167]


def test_an_undeclared_fall_of_the_same_size_is_still_a_fall() -> None:
    """No declaration for this ratchet, or other values: the series is unchanged."""
    assert since(FALL, "a", "x.json", []) == FALL
    assert since(FALL, "a", "y.json", STEP) == FALL
    assert since(FALL, "b", "x.json", STEP) == FALL
    assert since([264, 160], "a", "x.json", STEP) == [264, 160]


def test_a_declared_drop_earns_no_paydown_credit() -> None:
    """Judged whole, the drop reads as a fall of 97; from the declaration, only what fell after.

    From the declared step the series is 168, 168, 167: it fell one since, which is a real
    payment and counts, and the 96 of the step does not.
    """
    whole = verdict(FALL, WINDOW, 0)
    restarted = verdict(since(FALL, "a", "x.json", STEP), WINDOW, 0)
    assert whole[1] == FALL[2] - FALL[-1]
    assert restarted[1] == FALL[3] - FALL[-1]
    assert restarted[1] < whole[1]


def test_a_fall_after_the_declared_step_is_still_credited() -> None:
    """Payment made after the restart counts: 168 down to 160 over the window is a fall of 8."""
    later = [270, 264, 168, 168, 168, 160]
    restarted = since(later, "a", "x.json", STEP)
    assert restarted == [168, 168, 168, 160]
    assert verdict(restarted, WINDOW, 0)[1] == 168 - 160


def test_the_substrate_header_fix_is_declared() -> None:
    """The tsv whose census counted its header line restarts its history at 466 to 465 (W1269)."""
    table = "scripts/selftest_reach_baseline.tsv"
    steps = [
        (old, new)
        for repo, file, old, new, _ in DECLARED
        if repo == "substrate" and file == table
    ]
    assert steps == [(466, 465)]
    assert since([470, 466, 465, 464], "substrate", table, DECLARED) == [465, 464]


def test_every_declaration_kept_gives_its_reason() -> None:
    """A declaration without a reason is a hidden exemption."""
    assert all(entry[4] for entry in DECLARED)
