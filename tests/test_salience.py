"""nemik:W240: the flow model beside the old downstream weight, on a fleet small enough to solve by hand."""

from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path

import installed
import pytest
from rdflib import Graph

from nemik.check import survey
from nemik.rank import load_weights
from nemik.salience import ask_effect, audit, show


def _pf(state: Path, *args: str) -> None:
    cmd = [*installed.script("mikemol-paths-forward"), "--state", str(state), *args]
    assert (
        subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0
    )


def _wait(state: Path, card: str, on: list[str]) -> None:
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


def _queue(tmp_path: Path, titles: tuple[str, ...]) -> Path:
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    for title in titles:
        _pf(state, "--add", title, "--next", "do it")
    return state


def _fleet(tmp_path: Path) -> Path:
    # W1, W2 ready. W3 needs both (a conjunctive split). W4 needs W1 only.
    state = _queue(tmp_path, ("one", "two", "three", "four"))
    _wait(state, "W3", ["W1", "W2"])
    _wait(state, "W4", ["W1"])
    return tmp_path


def _ask_fleet(tmp_path: Path) -> Path:
    # W1, W2 ready. W3 needs W1, W4 needs W2: a tie, so W1 first. The ask W5 needs W2 as well.
    state = _queue(tmp_path, ("one", "two", "three", "four", "the ask"))
    for card, on in (("W3", "W1"), ("W4", "W2"), ("W5", "W2")):
        _wait(state, card, [on])
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


def test_an_ask_shows_what_it_needs_and_whom_it_displaces(tmp_path: Path) -> None:
    effect = ask_effect(_graph(_ask_fleet(tmp_path)), "a", "a:W5")
    local = Fraction(load_weights().local)
    assert effect.needs == [("a:W2", local)]
    assert effect.displaced == [("a:W1", 1, 2)]
    assert not effect.stranded


def test_an_ask_outside_the_ranking_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="injects no demand"):
        ask_effect(_graph(_ask_fleet(tmp_path)), "a", "a:W99")


def test_nemik_rank_ask_prints_needs_and_overrides(tmp_path: Path) -> None:
    done = installed.run(
        "nemik-rank", "a", "--ask", "a:W5", "--root", str(_ask_fleet(tmp_path))
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "needs a:W2" in done.stdout
    assert "overrides a:W1: position 1 without the ask, 2 with it" in done.stdout
