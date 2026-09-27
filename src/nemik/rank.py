"""Cross-repo downstream weight for ranking a queue's ready items (nemik:W34).

mtools' own ordering (mtools:W51 `model.leverage`) counts one queue's immediate edges. This module
adds the layer only nemik can see: the transitive closure across every workstream, with an edge
into another repo weighted by `data/rank-weights.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class Weights:
    local: int
    peer: int


def load_weights(text: str | None = None) -> Weights:
    """Read the edge weights; `text` overrides the packaged file (for tests)."""
    if text is None:
        text = files("nemik.data").joinpath("rank-weights.toml").read_text()
    data = tomllib.loads(text)
    return Weights(local=int(data["local"]), peer=int(data["peer"]))
