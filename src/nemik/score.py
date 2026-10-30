# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W131 (luthen-observability:W190): a waypoint's WV:1 vector -> a priority band.

mtools stores and validates the vector (mikemol.pathsforward.vector, mtools:W248); nemik owns the
band table (data/bands.toml) and everything built on it: rank composition (W132) and the ordering
guarantees `nemik-rank --check` enforces (W133). The vector is parsed only by mtools' parser.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib.resources import files

from mikemol.pathsforward.model import RefusedError
from mikemol.pathsforward.vector import parse


@dataclass(frozen=True)
class Bands:
    """The urgency bands from bands.toml: their order, the rules for each and the two fallbacks."""

    order: tuple[str, ...]
    rules: dict[str, tuple[dict[str, frozenset[str]], ...]]
    unscored: str
    unmatched: str
    # the `file:<ratchet>` tags of the ratchets the repo being ranked is behind on (nemik:W993)
    behind: frozenset[str] = frozenset()

    def rank(self, band: str) -> int:
        """0 is most urgent.

        Returns:
            The band's position in the declared order.

        """
        return self.order.index(band)

    def watching(self, behind: frozenset[str]) -> Bands:
        """Say which ratchets the repo being ranked is behind on.

        Returns:
            These bands with the behind tags set, so a card that pays one down takes velocity.

        """
        return Bands(self.order, self.rules, self.unscored, self.unmatched, behind)


def _table(value: object) -> dict[str, object]:
    """Read a TOML value as a table, or an empty one when it is anything else.

    Returns:
        The table's entries, keyed by string.

    """
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _tables(value: object) -> list[dict[str, object]]:
    """Read a TOML value as an array of tables, or an empty list when it is anything else.

    Returns:
        One table per element.

    """
    return [_table(v) for v in value] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    """Read a TOML value as an array of strings, or an empty list when it is anything else.

    Returns:
        One string per element.

    """
    return [str(v) for v in value] if isinstance(value, list) else []


def _text(value: object) -> str | None:
    """Read an optional TOML string.

    Returns:
        The value as a string, or None when it is absent.

    """
    return None if value is None else str(value)


def _rule(value: dict[str, object]) -> dict[str, frozenset[str]]:
    """Read one rule table: each metric to the set of values it allows.

    Returns:
        The rule, keyed by metric.

    """
    return {m: frozenset(_strings(v)) for m, v in value.items()}


def load_bands(text: str | None = None) -> Bands:
    """Read the band rules from bands.toml: the order, each band's rules and the two fallbacks.

    Args:
        text: The TOML text to read; None reads the packaged bands.toml.

    Returns:
        The bands, with each band's rules as tuples of method to frozenset of values.

    Raises:
        ValueError: when unscored or unmatched names a band that is not in order, or the file
            holds a band that is not in order.

    """
    if text is None:
        text = files("nemik.data").joinpath("bands.toml").read_text()
    d = _table(tomllib.loads(text))
    order = tuple(_strings(d["order"]))
    listed = _table(d.get("band"))
    rules = {b: tuple(_rule(r) for r in _tables(listed.get(b))) for b in order}
    for key in ("unscored", "unmatched"):
        if d[key] not in order:
            msg = f"bands.toml: {key} = {d[key]!r} is not in order"
            raise ValueError(msg)
    stray = set(listed) - set(order)
    if stray:
        msg = f"bands.toml: bands {sorted(stray)} are not in order"
        raise ValueError(msg)
    return Bands(order, rules, str(d["unscored"]), str(d["unmatched"]))


def band(vector: str | None, bands: Bands) -> tuple[str, str]:
    """(band, why) for a vector; why is 'unscored', 'invalid: ...', 'unmatched' or the rule matched.

    Returns:
        (band, why): the unscored band for a missing or invalid vector, the first band whose
        rule matches, else the unmatched band.

    """
    if not vector:
        return bands.unscored, "unscored"
    try:
        values = parse(vector)
    except RefusedError as e:
        # mtools' --check reports the bad vector to its owner; here it ranks as unscored, visibly.
        return bands.unscored, f"invalid: {e}"
    for b in bands.order:
        for rule in bands.rules[b]:
            if _matches(values, rule):
                return b, "/".join(
                    f"{m}:{'|'.join(sorted(a))}" for m, a in rule.items()
                )
    return bands.unmatched, "unmatched"


# nemik:W1077: a card whose owner tagged it `touches: velocity` is in the velocity band, which
# bands.toml lists above critical: the operator's order (host 695f3e0a line 100702) is that velocity
# work comes before the work it carries. The owner's tag is the declaration, so nemik keeps no list.
VELOCITY = "velocity"


def tagged_band(
    b: str, why: str, touches: set[str], behind: frozenset[str] = frozenset()
) -> tuple[str, str]:
    """Move a card into the velocity band when its owner tagged it so or it pays a behind ratchet.

    A paydown card is tagged `file:<the ratchet file>` (the fleet loop prompt), and a repo behind
    its required fall is owed that paydown ahead of feature work (operator 2026-10-24, host
    695f3e0a lines 92679 and 93406), beside velocity and not above it (line 100702): nemik:W993.

    Args:
        b: The band the card's vector gave.
        why: Why it gave that band.
        touches: The card's touches.
        behind: The `file:<ratchet>` tags of the ratchets its repo is behind on.

    Returns:
        (velocity, why) when the touches carry the velocity tag or a behind ratchet's file tag;
        otherwise the band and why given.

    """
    if VELOCITY in touches:
        return VELOCITY, "touches velocity"
    for tag in sorted(touches):
        file = tag.removesuffix("!w")
        if file in behind:
            return VELOCITY, f"pays down {file}, which is behind"
    return b, why


def _matches(values: dict[str, str], rule: dict[str, frozenset[str]]) -> bool:
    """Say whether a rule matches: every metric it names has one of the listed values.

    Returns:
        True when every metric the rule names has one of its listed values.

    """
    return all(values[m] in allowed for m, allowed in rule.items())


@dataclass(frozen=True)
class Policy:
    """An item class that blocks the ready items sharing a surface with its open members (W133)."""

    name: str
    tag: str | None
    rules: tuple[dict[str, frozenset[str]], ...]
    # nemik:W138 (luthen's letter, section 3): when set, only dependents carrying one of these
    # touches tags are blocked ("no tenant-facing rollout while a trust-boundary item is open");
    # empty blocks every dependent on a shared surface, as W133 did.
    only: frozenset[str] = frozenset()

    def blocks(self, touches: set[str]) -> bool:
        """Whether a dependent with these touches is in the class's scope at all.

        Returns:
            True when the class has no `only` tags or the touches carry one of them.

        """
        return not self.only or bool(self.only & touches)

    def member(self, vector: str | None, touches: set[str]) -> bool:
        """In the class when it carries the tag, or its vector matches one of the rules.

        Returns:
            True for a card tagged with the class, or whose valid vector matches a rule.

        """
        if self.tag is not None and self.tag in touches:
            return True
        try:
            values = parse(vector) if vector else None
        except RefusedError:
            values = (
                None  # an invalid vector is unscored (band()); it proves no membership
            )
        return values is not None and any(_matches(values, r) for r in self.rules)


@dataclass(frozen=True)
class Guarantees:
    """The bands.toml guarantee: the floor band and the policies that block shared surfaces."""

    floor: str | None
    policies: tuple[Policy, ...]


def load_guarantees(text: str | None = None, bands: Bands | None = None) -> Guarantees:
    """Read [guarantee] and [[policy]] from bands.toml (nemik:W133); `text` overrides it.

    Returns:
        The floor band (or None) and one Policy per [[policy]] table.

    """
    if text is None:
        text = files("nemik.data").joinpath("bands.toml").read_text()
    bands = bands or load_bands(text)
    d = _table(tomllib.loads(text))
    floor = _text(_table(d.get("guarantee")).get("floor"))
    if floor is not None and floor not in bands.order:
        msg = f"bands.toml: guarantee.floor = {floor!r} is not in order"
        raise ValueError(msg)
    policies = tuple(
        Policy(
            str(p["class"]),
            _text(p.get("tag")),
            tuple(_rule(r) for r in _tables(p.get("vector"))),
            frozenset(_strings(p.get("only"))),
        )
        for p in _tables(d.get("policy"))
    )
    return Guarantees(floor, policies)
