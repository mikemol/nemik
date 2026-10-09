"""nemik:W240: the flow model beside the old downstream weight, on a fleet small enough to solve by hand."""

from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path

import installed
from rdflib import Graph

from nemik.check import survey
from nemik.rank import load_weights
from nemik.salience import audit, show


def _pf(state: Path, *args: str) -> None:
    cmd = [*installed.script("mikemol-paths-forward"), "--state", str(state), *args]
    assert (
        subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0
    )


def _fleet(tmp_path: Path) -> Path:
    # W1, W2 ready. W3 needs both (a conjunctive split). W4 needs W1 only.
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    for title in ("one", "two", "three", "four"):
        _pf(state, "--add", title, "--next", "do it")
    for card, on in (("W3", ["W1", "W2"]), ("W4", ["W1"])):
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
    return tmp_path


def _graph(root: Path) -> Graph:
    g = Graph()
    for _, qg, _ in survey(root):
        if qg is not None:
            g += qg
    return g


def test_a_conjunctive_card_splits_its_demand_and_a_sole_dependent_does_not(
    tmp_path: Path,
) -> None:
    result = audit(_graph(_fleet(tmp_path)), "a")
    local = Fraction(load_weights().local)
    by_ref = {r.ref: r for r in result.rows}
    assert by_ref["a:W1"].old == 2 * local
    assert by_ref["a:W2"].old == local
    assert by_ref["a:W1"].new == local * Fraction(3, 2)
    assert by_ref["a:W2"].new == local / 2
    assert result.flow.stranded == {}


def test_both_arms_agree_when_the_split_does_not_change_the_order(
    tmp_path: Path,
) -> None:
    result = audit(_graph(_fleet(tmp_path)), "a")
    assert result.old_order() == result.new_order() == ["a:W1", "a:W2"]
    assert result.disagreements() == []


def test_display_rounds_but_the_value_stays_exact() -> None:
    value = Fraction(1, 3)
    assert show(value) == "0.3333"
    assert value * 3 == 1


def test_nemik_rank_flow_prints_both_arms(tmp_path: Path) -> None:
    done = installed.run("nemik-rank", "a", "--flow", "--root", str(_fleet(tmp_path)))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "flow a: 2 ready" in done.stdout
    assert "0 pair(s) ordered differently" in done.stdout
