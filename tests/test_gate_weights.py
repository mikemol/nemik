# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W253: a recorded gap weighs what rank-weights.toml [residue] says for its gate."""

from __future__ import annotations

import subprocess
from fractions import Fraction
from typing import TYPE_CHECKING

import installed
from rdflib import Graph

from nemik.check import survey
from nemik.rank import load_weights
from nemik.salience import audit, load_gate_weights

if TYPE_CHECKING:
    from pathlib import Path


def _pf(state: Path, *args: str) -> None:
    cmd = [*installed.script("mikemol-paths-forward"), "--state", str(state), *args]
    assert (
        subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0
    )


def _graph(tmp_path: Path) -> Graph:
    # W1 is ready; W2 waits on it, so W2's demand (its class weight) lands on W1.
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    for title in ("one", "two"):
        _pf(state, "--add", title, "--next", "do it")
    _pf(
        state,
        "--update",
        "W2",
        "--status",
        "blocked",
        "--blocked-kind",
        "agent",
        "--blocked-on",
        "W1",
    )
    g = Graph()
    for _, qg, _ in survey(tmp_path):
        if qg is not None:
            g += qg
    return g


def test_the_packaged_weights_skip_the_universal_gates() -> None:
    """The packaged weights skip the universal gates."""
    weights = load_gate_weights()
    assert weights["constructible"] == 1
    assert weights["reachable"] == 1
    assert weights["observable"] == 0
    assert weights["coverable"] == 0


def test_an_unnamed_gate_weighs_one_and_a_zero_gate_adds_nothing(
    tmp_path: Path,
) -> None:
    """An unnamed gate weighs one and a zero gate adds nothing."""
    g = _graph(tmp_path)
    local = Fraction(load_weights().local)
    gaps: dict[str, list[dict[str, object]]] = {
        "a:W2": [
            {"gate": "constructible"},
            {"gate": "observable"},
            {"gate": "unheard-of"},
        ]
    }
    weights = {"constructible": Fraction(2), "observable": Fraction(0)}
    result = audit(g, "a", residue=gaps, gate_weights=weights)
    # W2's class demand plus constructible (2), observable (0), an unnamed gate (the default, 1).
    assert result.rows[0].new == local + 2 + 0 + 1


def test_text_overrides_the_packaged_file() -> None:
    """Text overrides the packaged file."""
    assert load_gate_weights("[residue]\nreachable = 3\n") == {"reachable": Fraction(3)}
