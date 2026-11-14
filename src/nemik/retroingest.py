# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W982: the retros a queue holds, as the triples the retro shapes judge.

A queue document carries a `retros` list beside `waypoints` (the record form settled with mtools in
docs/retro-audit.md): id, card, trigger, root, contributing, precommit, frozen_timeline, delta,
sustain, enforcement_layer, recurring, one_off, findings (finding_card, finding_owner, due,
finding_witness, certify_change) and handoff (instrument, channel, operator). This reads one into
`(subject, predicate, object, is_node)` tuples of text: nemik.adapter turns them into rdflib
terms, so this stays pure (builtin types only, no import but nemik.tomlview) and the Codon census
compiles it.

⚑ ONLY A RETRO THAT CARRIES A PRECOMMIT IS READ (the scaffold form). Measured 2026-11-13 over the
493 retros of nemik's queue: 449 are the older free form with no precommit, no delta, no sustain and
no frozen timeline, and the shapes give 524 Violations on them, the older form being history and not
a live defect. The 44 that carry a precommit are held to the shapes. The cut-over is `in_scope`; a
back-fill rule for the older retros is a separate decision (nemik:W982).

A predicate `a` means rdf:type and its object is the class name. A recurring or one_off flag is the
text `true` when it is the JSON boolean true and absent otherwise, which is what the G9 shape reads.
"""

from nemik.tomlview import strings, table, tables

# subject, predicate, object, and whether the object is a node (else a literal)
Triple = tuple[str, str, str, bool]

# (record key, vocabulary predicate) pairs, as lists: the pinned Codon rejects the variable-length
# tuple type a tuple of pairs would need in a signature
TEXT_FIELDS = [
    ("trigger", "trigger"),
    ("root", "root"),
    ("precommit", "precommit"),
    ("frozen_timeline", "frozenTimeline"),
    ("enforcement_layer", "enforcementLayer"),
    ("delta", "delta"),
]
LIST_FIELDS = [("contributing", "contributing"), ("sustain", "sustain")]
FLAG_FIELDS = [("recurring", "recurring"), ("one_off", "oneOff")]
FINDING_FIELDS = [
    ("finding_card", "findingCard"),
    ("finding_owner", "findingOwner"),
    ("due", "due"),
    ("finding_witness", "findingWitness"),
    ("certify_change", "certifyChange"),
]
HANDOFF_FIELDS = [
    ("instrument", "handoffInstrument"),
    ("channel", "handoffChannel"),
    ("operator", "handoffOperator"),
    ("self_probe", "selfProbe"),
]


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def in_scope(retro: dict[str, object]) -> bool:
    """Say whether a retro is in the scaffold form the shapes judge (it carries a precommit).

    Returns:
        True when the retro's precommit is a non-empty text.

    """
    return bool(_text(retro.get("precommit")).strip())


def triples(retro: dict[str, object]) -> list[Triple]:
    """Read one retro as triples; a retro with no id reads as none.

    Returns:
        The retro's triples: its class, its text, list and flag fields, one RetroFinding per
        finding and a RetroHandoff when it has a handoff.

    """
    ident = _text(retro.get("id"))
    if not ident:
        return []
    subject = f"retro/{ident}"
    out: list[Triple] = [(subject, "a", "Retro", False)]
    out.extend(_texts(subject, retro, TEXT_FIELDS))
    for key, predicate in LIST_FIELDS:
        out.extend((subject, predicate, item, False) for item in strings(retro.get(key)))
    out.extend(
        (subject, predicate, "true", False)
        for key, predicate in FLAG_FIELDS
        if retro.get(key) is True
    )
    for number, finding in enumerate(tables(retro.get("findings"))):
        out.extend(_child(subject, f"finding/{number}", "RetroFinding", "finding"))
        out.extend(_texts(f"{subject}/finding/{number}", finding, FINDING_FIELDS))
    handoff = table(retro.get("handoff"))
    if handoff:
        out.extend(_child(subject, "handoff", "RetroHandoff", "handoff"))
        out.extend(_texts(f"{subject}/handoff", handoff, HANDOFF_FIELDS))
    return out


def _texts(
    subject: str, fields: dict[str, object], names: list[tuple[str, str]]
) -> list[Triple]:
    # a literal triple for each named field that holds a non-empty text
    out: list[Triple] = []
    for key, predicate in names:
        text = _text(fields.get(key))
        if text:
            out.append((subject, predicate, text, False))
    return out


def _child(subject: str, path: str, cls: str, link: str) -> list[Triple]:
    # the class triple of a child node and the node triple that links it from its parent
    node = f"{subject}/{path}"
    return [(node, "a", cls, False), (subject, link, node, True)]


def all_triples(retros: object) -> list[Triple]:
    """Read a queue's retros list, the in-scope retros only.

    Returns:
        The triples of every retro that carries a precommit, in list order.

    """
    out: list[Triple] = []
    for retro in tables(retros):
        if in_scope(retro):
            out.extend(triples(retro))
    return out
