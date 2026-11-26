# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W985: the retros' findings by layer, and the recurring classes placed by layer."""

from nemik import retrolayers as rl

GATE_TOTAL = 27  # the live counts of 2026-11-22: gate 27, instructions 13, hook 4
INSTRUCTIONS_TOTAL = 13
HOOK_TOTAL = 4
RECURRING = 9
NO_CARD = ""


def _planted() -> list[rl.Row]:
    # recurring: gate A in three spellings of one text and gate B twice, instructions C twice,
    # instructions D once, hook E once (9), none citing a card; everything else at each layer is
    # a one-off finding
    recurring: list[rl.Row] = [
        ("A check was waived", "gate", True, NO_CARD),
        ("a  check was WAIVED", "gate", True, NO_CARD),
        ("A check was waived ", "Gate", True, NO_CARD),
        ("A failing test was rerun", "gate", True, NO_CARD),
        ("A failing test was rerun", "gate", True, NO_CARD),
        ("The rule was not read", "instructions", True, NO_CARD),
        ("The rule was not read", "instructions", True, NO_CARD),
        ("The note was stale", "instructions", True, NO_CARD),
        ("A hook was bypassed", "hook", True, NO_CARD),
    ]
    rows = list(recurring)
    for layer, total in (
        ("gate", GATE_TOTAL),
        ("instructions", INSTRUCTIONS_TOTAL),
        ("hook", HOOK_TOTAL),
    ):
        have = sum(1 for _, got, _, _ in recurring if got.lower() == layer)
        rows += [
            (f"{layer} one-off {i}", layer, False, NO_CARD) for i in range(total - have)
        ]
    return rows


def test_the_counts_by_layer_include_the_layers_nothing_was_placed_at() -> None:
    """Gate 27, instructions 13, hook 4; memory and trigger are zero, not absent."""
    assert rl.layer_counts(_planted()) == [
        ("memory", 0),
        ("instructions", INSTRUCTIONS_TOTAL),
        ("trigger", 0),
        ("hook", HOOK_TOTAL),
        ("gate", GATE_TOTAL),
    ]


def test_a_layer_outside_the_vocabulary_is_counted_unplaced_not_dropped() -> None:
    """An unknown or empty layer is its own count."""
    rows: list[rl.Row] = [
        ("x", "gate", False, NO_CARD),
        ("y", "vibes", False, NO_CARD),
        ("z", "", True, NO_CARD),
    ]
    counts = dict(rl.layer_counts(rows))
    assert counts["gate"] == 1
    assert counts[rl.UNPLACED] == len(("vibes", ""))
    assert rl.layer_of(" HOOK ") == "hook"


def test_cardless_findings_group_by_exact_text_and_say_so() -> None:
    """Nine recurring findings make five classes on text; case and spacing fold, not wording."""
    found = rl.recurring_classes(_planted())
    assert sum(count for _, _, count, _ in found) == RECURRING
    assert found == [
        ("A check was waived", "gate", 3, "text"),
        ("The rule was not read", "instructions", 2, "text"),
        ("A failing test was rerun", "gate", 2, "text"),
        ("The note was stale", "instructions", 1, "text"),
        ("A hook was bypassed", "hook", 1, "text"),
    ]


def test_two_wordings_of_one_class_group_when_they_cite_one_card() -> None:
    """The card a finding came back against is the class: reworded, it is still one."""
    rows: list[rl.Row] = [
        ("A check was waived", "gate", True, "nemik:W10"),
        ("The gate check got waived again", "gate", True, "nemik:W10"),
        ("Waiver of the check, third time", "gate", True, " nemik:W10 "),
        ("A check was waived", "gate", True, NO_CARD),
    ]
    assert rl.recurring_classes(rows) == [
        ("A check was waived", "gate", 3, "card"),
        ("A check was waived", "gate", 1, "text"),
    ]


def test_the_same_card_at_two_layers_is_two_classes() -> None:
    """The layer a retro names is part of the class, with a card or without one."""
    rows: list[rl.Row] = [
        ("same", "gate", True, "nemik:W10"),
        ("same", "hook", True, "nemik:W10"),
        ("same", "gate", True, NO_CARD),
        ("same", "hook", True, NO_CARD),
    ]
    found = rl.recurring_classes(rows)
    assert len(found) == len(rows)
    # equal counts order by the layer's place in the vocabulary: hook before gate
    assert [(layer, basis) for _, layer, _, basis in found] == [
        ("hook", "card"),
        ("hook", "text"),
        ("gate", "card"),
        ("gate", "text"),
    ]
