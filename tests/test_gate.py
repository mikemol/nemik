"""Gate tests: the output contracts other workstreams read.

luthen's W81 witness parses nemik-check's exit code and provenance lines; other repos' ticks read
nemik-inbound's UNCLAIMED column (paths-forward-loop §4.2). These tests pin both over a fixture
root in the export layout (<root>/<repo>/paths-forward.json), which is what the pod reads.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def waypoint(sym: str, **kw) -> dict:
    return {
        "symbol": sym, "title": f"{sym} title", "status": "ready", "enables": [], "touches": [],
        "blocked_on": [], "blocked_kind": None, "next_bounded_step": "", "evidence": "",
        "issued_at": "2026-09-26T00:00:00Z", "last_worked": "2026-09-26T00:00:00Z", "ticks_blocked": 0,
    } | kw


def write_queue(root: Path, repo: str, *wps: dict) -> None:
    d = root / repo
    d.mkdir(parents=True)
    counter = max((int(w["symbol"][1:]) for w in wps), default=0)
    (d / "paths-forward.json").write_text(json.dumps({
        "version": 1, "project_root": f"/fixture/{repo}", "counter": counter,
        "waypoints": list(wps), "residue": [],
    }))


def run(tool: str, root: Path, *argv: str) -> subprocess.CompletedProcess:
    mod, fn = {"check": ("nemik.check", "main"), "inbound": ("nemik.blocks", "main"),
               "operator": ("nemik.blocks", "operator_main")}[tool]
    return subprocess.run([sys.executable, "-c", f"from {mod} import {fn}; {fn}()", "--root", str(root), *argv],
                          capture_output=True, text=True)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    # alpha:W1 waits on beta:W1, which claims it; alpha:W2 waits on beta with nothing claiming it.
    write_queue(tmp_path, "alpha",
                waypoint("W1", status="blocked", blocked_on=["beta:W1"], blocked_kind="agent"),
                waypoint("W2", status="blocked", blocked_on=["beta"], blocked_kind="agent"))
    write_queue(tmp_path, "beta", waypoint("W1", enables=["alpha:W1"]))
    return tmp_path


def test_check_conforming_exits_zero_with_provenance(root: Path) -> None:
    r = run("check", root)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("provenance: nemik ")
    assert "provenance: queue alpha untracked-source" in lines
    assert "provenance: queue beta untracked-source" in lines
    assert any(l.startswith("OK        alpha") for l in lines)


def test_check_violation_exits_one_and_names_repo(root: Path) -> None:
    # enables into a symbol no workstream has is a Violation (shapes.ttl); most shapes are Warnings.
    write_queue(root, "gamma", waypoint("W1", enables=["alpha:W9"]))
    r = run("check", root)
    assert r.returncode == 1, r.stdout + r.stderr
    assert any(l.startswith("VIOLATES  gamma") for l in r.stdout.splitlines())


def test_inbound_keeps_unclaimed_column_and_hint(root: Path) -> None:
    r = run("inbound", root, "beta")
    assert r.returncode == 0, r.stderr
    rows = {l.split()[2]: l for l in r.stdout.splitlines()}
    assert rows["alpha:W1"].split()[3] == "beta:W1"
    assert rows["alpha:W2"].split()[3] == "UNCLAIMED"
    assert rows["alpha:W2"].endswith("-- waiting on you, claim with --enables alpha:W2")


def test_operator_categories(tmp_path: Path) -> None:
    write_queue(tmp_path, "alpha",
                waypoint("W1", status="blocked", blocked_on=["operator: decide ship A or B"], blocked_kind="human"),
                waypoint("W2", status="blocked", blocked_on=["operator"], blocked_kind="human"))
    r = run("operator", tmp_path, "--json")
    assert r.returncode == 0, r.stderr
    asks = json.loads(r.stdout)
    asks = asks if isinstance(asks, list) else asks["asks"]
    cat = {a["ref"]: a["category"] for a in asks}
    assert cat == {"alpha:W1": "needs-you", "alpha:W2": "unstated"}
