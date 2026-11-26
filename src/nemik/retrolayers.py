# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W985: gate G9 measured fleet-wide: the retros' findings by the layer their measure is at.

A retro finding names the enforcement layer its measure lives at: memory, instructions, trigger,
hook or gate. A finding marked recurring is a CLASS that came back after a fix, so the layer it was
placed at did not hold it. This is the pure reduction over (finding text, layer, recurring, card)
rows read from the ingested retros: how many findings sit at each layer, and the recurring classes
with the layer each retro names.

WHAT GROUPS. Recurring findings group by the card they cite (the retro's finding_card: the G7
commitment the finding came back against) together with the layer, so one class reworded across
retros is still one class. A row with no card falls back to its EXACT text (lower-cased, whitespace
collapsed) with the layer: two different wordings of one class do not group there, so a card-less
class that came back reworded reads as several one-off classes and recurrence is UNDERCOUNTED. Each
class says which basis it grouped on, so a report can label the text ones "grouped by exact text
(may split one class)". Strings, ints, bools and lists only, so the Codon census compiles it.
"""

LAYERS = ["memory", "instructions", "trigger", "hook", "gate"]
UNPLACED = "unplaced"  # a finding whose layer is not one of LAYERS (or is empty)
BY_CARD = "card"
BY_TEXT = "text"

Row = tuple[str, str, bool, str]


def normal(text: str) -> str:
    """Normalise a finding's text for the exact-text fallback.

    Returns:
        The text lower-cased with runs of whitespace made single spaces. Only spelling of case and
        spacing is folded; a different wording stays different.

    """
    return " ".join(text.split()).lower()


def layer_of(layer: str) -> str:
    """Place a retro's named layer in the vocabulary.

    Returns:
        The layer, lower-cased, when it is one of LAYERS, else UNPLACED.

    """
    named = layer.strip().lower()
    return named if named in LAYERS else UNPLACED


def layer_counts(rows: list[Row]) -> list[tuple[str, int]]:
    """Count the findings at each layer.

    Args:
        rows: (finding text, layer, recurring, cited card) per finding.

    Returns:
        (layer, count) for every layer of LAYERS in vocabulary order, zeros included (a layer
        nothing was placed at is a result, not an absence), then UNPLACED when any finding fell
        outside the vocabulary.

    """
    counts: dict[str, int] = dict.fromkeys(LAYERS, 0)
    unplaced = 0
    for _, layer, _, _ in rows:
        placed = layer_of(layer)
        if placed == UNPLACED:
            unplaced += 1
        else:
            counts[placed] += 1
    out = [(layer, counts[layer]) for layer in LAYERS]
    return [*out, (UNPLACED, unplaced)] if unplaced else out


def class_key(text: str, layer: str, card: str) -> str:
    """Name the class a recurring finding belongs to.

    Returns:
        The cited card and the layer when the row has a card, else the exact text and the layer;
        the two never share a key.

    """
    placed = layer_of(layer)
    named = card.strip()
    if named:
        return BY_CARD + "\n" + named + "\n" + placed
    return BY_TEXT + "\n" + normal(text) + "\n" + placed


def recurring_classes(rows: list[Row]) -> list[tuple[str, str, int, str]]:
    """Group the recurring findings into classes (see WHAT GROUPS in the module docstring).

    Args:
        rows: (finding text, layer, recurring, cited card) per finding.

    Returns:
        (finding text as first seen, layer, how many recurring findings, basis BY_CARD or BY_TEXT)
        per class, most recurrences first, then by layer in vocabulary order, then text. Findings
        not marked recurring are left out.

    """
    shown: dict[str, str] = {}
    counts: dict[str, int] = {}
    for text, layer, recurring, card in rows:
        if not recurring:
            continue
        key = class_key(text, layer, card)
        shown.setdefault(key, text.strip())
        counts[key] = counts.get(key, 0) + 1
    classes = [
        (shown[key], key.rsplit("\n", 1)[1], count, key.split("\n", 1)[0])
        for key, count in counts.items()
    ]
    return sorted(classes, key=_class_order)


def _class_order(found: tuple[str, str, int, str]) -> tuple[int, int, str]:
    """Order classes: most recurrences first, then the layer's place in the vocabulary, then text.

    Returns:
        The sort key of one (text, layer, count, basis) class.

    """
    order = [*LAYERS, UNPLACED]
    return -found[2], order.index(found[1]), normal(found[0])
