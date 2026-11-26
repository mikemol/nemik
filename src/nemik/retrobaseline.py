# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2357: historic retro handoffs that predate the self-probe rule read as Info, not VIOLATES.

nemik:RetroHandoffProbeShape (the self-probe half of W755's gate G8) refuses a retro handoff to
another operator that records no self probe executed-and-failed. The rule was defined in f1b458a6
(2026-10-19) and first judged real retros in 171704e7 (2026-11-14, W982), and the field it reads
(handoff.self_probe) was documented nowhere a retro's author would see until this card, so the
retros that broke it when it was baselined were written before their authors could know it. Retros
are write-once (the reviewer's record is never hand-edited), so no session can repair one, and a
Violation pages the operator over a record nobody can act on (the host's ruling, relayed in
inbox/2026-11-19-github-00-retro-handoff-shape-flags-history.md).

The committed baseline (src/nemik/data/retro-handoff-baseline.json) lists those retros, keyed by
repo and retro (`gcalculus:R12`). A result is read as Info only by its IDENTITY: the shape that
produced it is RetroHandoffProbeShape and its focus is a baselined retro's handoff. The message
text is never read, so rewording it cannot change what is demoted, and another shape's result on
the same handoff keeps its severity. The baseline only shrinks: it is a registered ratchet, and
tools/retro_handoff_baseline.py can only drop ids from it.

Pure: builtin types only and no import, so the Codon census compiles it.
"""

PROBE_SHAPE = "https://github.com/mikemol/nemik/ns#RetroHandoffProbeShape"
HISTORIC = (
    "historic, baselined (retros are write-once and this one predates the rule; "
    "src/nemik/data/retro-handoff-baseline.json, nemik:W2357): "
)
STALE = (
    "is in the retro handoff baseline but no longer breaks the self-probe rule: "
    "tools/retro_handoff_baseline.py --write drops it (the baseline only shrinks, nemik:W2357)"
)
PREFIX = "retro/"
SUFFIX = "/handoff"

# (severity, focus symbol, message), as nemik.check files them
Finding = tuple[str, str, str]
# a finding with the IRI of the shape that produced it
Row = tuple[str, str, str, str]


def retro_id(symbol: str) -> str:
    """Give the retro id a handoff's focus symbol names.

    Args:
        symbol: A handoff's focus symbol, such as `retro/gcalculus:R12/handoff`.

    Returns:
        The retro id (`gcalculus:R12`).

    Raises:
        ValueError: the symbol is not a retro handoff's, or names no retro: the probe shape only
            targets handoffs, so this is a shape defect, never a result to read past.

    """
    inner = symbol[len(PREFIX) : len(symbol) - len(SUFFIX)]
    if not (symbol.startswith(PREFIX) and symbol.endswith(SUFFIX) and inner):
        msg = f"not a retro handoff's focus: {symbol!r}"
        raise ValueError(msg)
    return inner


def is_probe(row: Row) -> bool:
    """Say whether a result is a Violation of the self-probe shape.

    Args:
        row: A result with the shape that produced it.

    Returns:
        True for a Violation whose source shape is RetroHandoffProbeShape.

    """
    severity, _, _, shape = row
    return severity == "Violation" and shape == PROBE_SHAPE


def demote(rows: list[Row], baseline: set[str]) -> list[Finding]:
    """Read the probe shape's Violations on baselined retros as Info; leave every other result.

    Args:
        rows: One repo's results, each with its source shape.
        baseline: The baselined retro ids.

    Returns:
        The findings in the same order, those of the probe shape on baselined retros as Info with
        the reason said.

    """
    out: list[Finding] = []
    for row in rows:
        severity, symbol, message, _ = row
        if is_probe(row) and retro_id(symbol) in baseline:
            out.append(("Info", symbol, HISTORIC + message))
        else:
            out.append((severity, symbol, message))
    return out


def violators(rows: list[Row]) -> list[str]:
    """List the retros the probe shape refuses, before any demotion.

    Args:
        rows: Results of any repos, each with its source shape.

    Returns:
        The sorted, distinct retro ids.

    """
    return sorted({retro_id(row[1]) for row in rows if is_probe(row)})


def stale(baseline: list[str], today: list[str]) -> list[str]:
    """List the baselined retros that no longer break the rule.

    Args:
        baseline: The committed ids.
        today: The ids the probe shape refuses now.

    Returns:
        The sorted baselined ids not refused today.

    """
    now = set(today)
    return sorted(ident for ident in baseline if ident not in now)


def shrink(baseline: list[str], today: list[str]) -> list[str]:
    """Drop the baselined ids that no longer break the rule; never add one.

    Args:
        baseline: The committed ids.
        today: The ids the probe shape refuses now.

    Returns:
        The sorted ids in both: the baseline can only shrink.

    """
    now = set(today)
    return sorted(ident for ident in baseline if ident in now)


# nemik:W2514: the second baseline, of retros with zero sustain rows (nemik:RetroSustainShape, gate
# G6). Same discipline as the handoff baseline: counted debt that only shrinks, read by the result's
# shape IRI and focus, never its message. The focus of this shape is the retro itself.
SUSTAIN_SHAPE = "https://github.com/mikemol/nemik/ns#RetroSustainShape"
SUSTAIN_PREFIX = "retro/"


def sustain_id(symbol: str) -> str:
    """Give the retro id a sustain result's focus symbol names.

    Args:
        symbol: A retro's focus symbol, such as `retro/github:R12`.

    Returns:
        The retro id (`github:R12`).

    Raises:
        ValueError: the symbol is not a retro's: the sustain shape targets retros, so this is a
            shape defect, never a result to read past.

    """
    inner = symbol[len(SUSTAIN_PREFIX) :]
    if not symbol.startswith(SUSTAIN_PREFIX) or not inner or "/" in inner:
        msg = f"not a retro's focus: {symbol!r}"
        raise ValueError(msg)
    return inner


def sustain_retros(rows: list[Row]) -> list[str]:
    """List the retros the sustain shape judges thin, at any severity.

    Args:
        rows: Results of any repos, each with its source shape.

    Returns:
        The sorted, distinct retro ids whose result came from RetroSustainShape. Any severity: the
        shape reads Info today, and the seed is the set it names now.

    """
    return sorted({sustain_id(row[1]) for row in rows if row[3] == SUSTAIN_SHAPE})


SUSTAIN_HISTORIC = (
    "thin, baselined (retros are write-once and this one predates the sustain rule; "
    "src/nemik/data/retro-sustain-baseline.json, nemik:W2514): "
)
SUSTAIN_STALE = (
    "is in the retro sustain baseline but is no longer thin: "
    "tools/retro_sustain_baseline.py --write drops it (the baseline only shrinks, nemik:W2514)"
)


def is_thin(row: Row) -> bool:
    """Say whether a result is a Violation of the sustain shape.

    Args:
        row: A result with the shape that produced it.

    Returns:
        True for a Violation whose source shape is RetroSustainShape.

    """
    severity, _, _, shape = row
    return severity == "Violation" and shape == SUSTAIN_SHAPE


def demote_thin(rows: list[Row], baseline: set[str]) -> list[Row]:
    """Read the sustain shape's Violations on baselined retros as Info; leave every other result.

    A thin retro outside the baseline keeps its Violation: the baseline is counted debt, not a
    silent Info. The result still carries each row's shape, so `demote` can read the same rows
    for the handoff baseline after this.

    Args:
        rows: One repo's results, each with its source shape.
        baseline: The baselined retro ids of the sustain shape.

    Returns:
        The rows in the same order, a baselined thin retro's with severity Info and the reason said.

    """
    out: list[Row] = []
    for row in rows:
        severity, symbol, message, shape = row
        if is_thin(row) and sustain_id(symbol) in baseline:
            out.append(("Info", symbol, SUSTAIN_HISTORIC + message, shape))
        else:
            out.append((severity, symbol, message, shape))
    return out
