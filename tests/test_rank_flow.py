"""nemik:W241: nemik-rank's `weight` objective is the flow salience when the composition says so."""

from __future__ import annotations

import subprocess
from pathlib import Path

import installed
import pytest
from rdflib import Graph

from nemik.check import survey
from nemik.rank import load_composition, load_weights, rank

TIERS = '[order]\ntiers = [["weight"]]\n'


def _pf(state: Path, *args: str) -> None:
    cmd = [*installed.script("mikemol-paths-forward"), "--state", str(state), *args]
    assert (
        subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0
    )


def _fleet(tmp_path: Path) -> Graph:
    # A (W1), E (W2), B (W3) are ready. W4, W5, W6 each need BOTH A and E (three shared sources);
    # W7 and W8 each need B alone. Old weight: A 3, E 3, B 2. Flow: A 3/2, E 3/2, B 2.
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    for title in ("A", "E", "B", "s1", "s2", "s3", "t1", "t2"):
        _pf(state, "--add", title, "--next", "do it")
    needs = {
        "W4": ["W1", "W2"],
        "W5": ["W1", "W2"],
        "W6": ["W1", "W2"],
        "W7": ["W3"],
        "W8": ["W3"],
    }
    for card, on in needs.items():
        _pf(
            state,
            "--update",
            card,
            "--status",
            "blocked",
            "--blocked-kind",
            "agent",
            "--blocked-on",
            *on,
        )
    g = Graph()
    for _, qg, _ in survey(tmp_path):
        if qg is not None:
            g += qg
    return g


def _order(g: Graph, model: str) -> list[str]:
    comp = load_composition(f'{TIERS}weight = "{model}"\n')
    return [r["symbol"] for r in rank(g, "a", load_weights(), comp, fruit_row=False)]


def test_the_downstream_arm_still_counts_a_shared_source_in_full(
    tmp_path: Path,
) -> None:
    assert _order(_fleet(tmp_path), "downstream") == ["W1", "W2", "W3"]


def test_the_flow_arm_splits_it_so_the_sole_dependents_win(tmp_path: Path) -> None:
    assert _order(_fleet(tmp_path), "flow") == ["W3", "W1", "W2"]


def test_a_composition_that_names_no_model_keeps_the_old_sum() -> None:
    assert load_composition(TIERS).weight_model == "downstream"


def test_an_unknown_model_is_refused() -> None:
    with pytest.raises(ValueError, match="weight must be one of"):
        load_composition(f'{TIERS}weight = "vibes"\n')


def test_the_packaged_composition_declares_flow() -> None:
    assert load_composition().weight_model == "flow"
