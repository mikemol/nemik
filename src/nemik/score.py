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
    order: tuple[str, ...]
    rules: dict[str, tuple[dict[str, frozenset[str]], ...]]
    unscored: str
    unmatched: str

    def rank(self, band: str) -> int:
        """0 is most urgent."""
        return self.order.index(band)


def load_bands(text: str | None = None) -> Bands:
    if text is None:
        text = files("nemik.data").joinpath("bands.toml").read_text()
    d = tomllib.loads(text)
    order = tuple(d["order"])
    rules = {
        b: tuple(
            {m: frozenset(v) for m, v in r.items()}
            for r in d.get("band", {}).get(b, [])
        )
        for b in order
    }
    for key in ("unscored", "unmatched"):
        if d[key] not in order:
            raise ValueError(f"bands.toml: {key} = {d[key]!r} is not in order")
    stray = set(d.get("band", {})) - set(order)
    if stray:
        raise ValueError(f"bands.toml: bands {sorted(stray)} are not in order")
    return Bands(order, rules, d["unscored"], d["unmatched"])


def band(vector: str | None, bands: Bands) -> tuple[str, str]:
    """(band, why) for a vector; why is 'unscored', 'invalid: ...', 'unmatched' or the rule matched."""
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


def _matches(values: dict[str, str], rule: dict[str, frozenset[str]]) -> bool:
    """A rule matches when every metric it names has one of the listed values."""
    return all(values[m] in allowed for m, allowed in rule.items())


@dataclass(frozen=True)
class Policy:
    """An item class that blocks the ready items sharing a surface with its open members (W133)."""

    name: str
    tag: str | None
    rules: tuple[dict[str, frozenset[str]], ...]
    # nemik:W138 (luthen's letter, section 3): when set, only dependents carrying one of these touches
    # tags are blocked ("no tenant-facing rollout while a trust-boundary item is open"); empty
    # blocks every dependent on a shared surface, as W133 did.
    only: frozenset[str] = frozenset()

    def blocks(self, touches: set[str]) -> bool:
        """Whether a dependent with these touches is in the class's scope at all."""
        return not self.only or bool(self.only & touches)

    def member(self, vector: str | None, touches: set[str]) -> bool:
        """In the class when it carries the tag, or its vector matches one of the rules."""
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
    floor: str | None
    policies: tuple[Policy, ...]


def load_guarantees(text: str | None = None, bands: Bands | None = None) -> Guarantees:
    """Read [guarantee] and [[policy]] from bands.toml (nemik:W133); `text` overrides it."""
    if text is None:
        text = files("nemik.data").joinpath("bands.toml").read_text()
    bands = bands or load_bands(text)
    d = tomllib.loads(text)
    floor = d.get("guarantee", {}).get("floor")
    if floor is not None and floor not in bands.order:
        raise ValueError(f"bands.toml: guarantee.floor = {floor!r} is not in order")
    policies = tuple(
        Policy(
            p["class"],
            p.get("tag"),
            tuple({m: frozenset(v) for m, v in r.items()} for r in p.get("vector", [])),
            frozenset(p.get("only", [])),
        )
        for p in d.get("policy", [])
    )
    return Guarantees(floor, policies)
