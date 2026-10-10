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


def _blocked_sharer(tmp_path: Path) -> Graph:
    # W1, W2 ready. W3 is blocked on the operator (a dead end, not workable). W4 needs W1 and W3,
    # W5 needs W2. If W3 absorbed demand, W1 would get 1/2 and W2 1, so W2 would lead; W3 cannot
    # be picked up, so W4's demand all goes to W1 and the tie falls to the lower symbol.
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    for title in ("one", "two", "ask", "needs both", "needs two"):
        _pf(state, "--add", title, "--next", "do it")
    _pf(
        state,
        "--update",
        "W3",
        "--status",
        "blocked",
        "--blocked-kind",
        "human",
        "--blocked-on",
        "operator: decide it",
    )
    for card, on in (("W4", ["W1", "W3"]), ("W5", ["W2"])):
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


def test_a_card_blocked_outside_the_graph_absorbs_no_demand(tmp_path: Path) -> None:
    assert _order(_blocked_sharer(tmp_path), "flow") == ["W1", "W2"]


def test_a_composition_that_names_no_model_keeps_the_old_sum() -> None:
    assert load_composition(TIERS).weight_model == "downstream"


def test_an_unknown_model_is_refused() -> None:
    with pytest.raises(ValueError, match="weight must be one of"):
        load_composition(f'{TIERS}weight = "vibes"\n')


def test_the_packaged_composition_declares_flow() -> None:
    assert load_composition().weight_model == "flow"


def _ask_fleet(tmp_path: Path) -> Graph:
    # W1 and W2 are ready leaves, equal in everything; the operator asked for W2.
    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    _pf(state, "--add", "plain", "--next", "do it")
    _pf(state, "--add", "asked", "--next", "do it", "--caused-by", "operator")
    g = Graph()
    for _, qg, _ in survey(tmp_path):
        if qg is not None:
            g += qg
    return g


def _ranked(g: Graph, operator: int) -> list[str]:
    weights = load_weights(
        f"local = 1\npeer = 2\npeer_blocked = 8\noperator = {operator}\n"
    )
    comp = load_composition(f'{TIERS}weight = "flow"\n')
    return [r["symbol"] for r in rank(g, "a", weights, comp, fruit_row=False)]


def test_an_operator_ask_is_a_demand_source_with_the_declared_weight(
    tmp_path: Path,
) -> None:
    g = _ask_fleet(tmp_path)
    no_term = _ranked(g, 0)  # a tie between equal leaves: the lower symbol leads
    assert no_term == ["W1", "W2"]
    assert _ranked(g, 15) == ["W2", "W1"]  # the ask carries its declared weight


def test_the_view_ships_each_ready_cards_flow_salience(tmp_path: Path) -> None:
    # nemik:W261: graph.json carries the salience the card absorbs, so the page can order by it.
    from nemik.serve import to_json

    doc = to_json(_fleet(tmp_path), {})
    by_symbol = {n["symbol"]: n for n in doc["nodes"] if n["state"] == "ready"}
    assert by_symbol["W3"]["salience"] == 2.0  # B absorbs both sole dependents' demand
    assert by_symbol["W1"]["salience"] == by_symbol["W2"]["salience"] == 1.5


def test_the_view_ships_the_current_across_each_dependency(tmp_path: Path) -> None:
    # nemik:W264: W7 and W8 each need only B (W3), so each dependency carries exactly their demand
    # of 1; W4 needs A and E equally, so it splits its demand of 1 in half across the two.
    from nemik.serve import to_json

    doc = to_json(_fleet(tmp_path), {})
    current = {
        (e["source"].rsplit("/", 1)[-1], e["target"].rsplit("/", 1)[-1]): e["current"]
        for e in doc["edges"]
        if "current" in e
    }
    assert current[("W7", "W3")] == 1.0
    assert current[("W4", "W1")] == current[("W4", "W2")] == 0.5


def test_the_view_weighs_the_edges_that_wait_on_the_operator(tmp_path: Path) -> None:
    # nemik:W298: W1 is an ask; W2 and W3 wait on it. The lane edge carries what the ask holds back
    # (2), and each waiter's edge into the ask carries its own demand (1).
    from nemik.serve import to_json

    (tmp_path / "a" / ".claude").mkdir(parents=True)
    state = tmp_path / "a" / ".claude" / "paths-forward.json"
    _pf(state, "--init")
    for title in ("ask", "w two", "w three"):
        _pf(state, "--add", title, "--next", "do it")
    _pf(
        state,
        "--update",
        "W1",
        "--status",
        "blocked",
        "--blocked-kind",
        "human",
        "--blocked-on",
        "operator: decide it",
    )
    for card in ("W2", "W3"):
        _pf(
            state,
            "--update",
            card,
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
    doc = to_json(g, {})
    (lane,) = [e for e in doc["edges"] if e["target"].startswith("operator:")]
    assert lane["current"] == 2.0
    into = [e for e in doc["edges"] if e["target"].endswith("/W1") and "current" in e]
    assert sorted(e["current"] for e in into) == [1.0, 1.0]
    assert doc["operator"][0]["salience"] == 2.0


def test_the_packaged_operator_weight_is_declared() -> None:
    assert load_weights().operator == 15
