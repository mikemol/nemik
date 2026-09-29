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
    rules = {b: tuple({m: frozenset(v) for m, v in r.items()} for r in d.get("band", {}).get(b, []))
             for b in order}
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
            if all(values[m] in allowed for m, allowed in rule.items()):
                return b, "/".join(f"{m}:{'|'.join(sorted(a))}" for m, a in rule.items())
    return bands.unmatched, "unmatched"
