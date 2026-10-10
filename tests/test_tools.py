from pathlib import Path

import installed
import pytest
from rdflib import Graph

from nemik.check import survey
from nemik.tools import COMMANDS, FILE_COMMANDS, run

# module:function -> the console script pyproject installs for it
SCRIPTS = {
    "nemik.rank:main": "nemik-rank",
    "nemik.overlaps:main": "nemik-overlaps",
    "nemik.blocks_cli:main": "nemik-inbound",
    "nemik.blocks_cli:operator_main": "nemik-operator",
    "nemik.wake:main": "nemik-wake",
    "nemik.check:main": "nemik-check",
    "nemik.metrics:main": "nemik-metrics",
    "nemik.floorasks:main": "nemik-floor-asks",
    "nemik.witnesses:main": "nemik-witnesses",
}


def _graph(root: Path) -> Graph:
    g = Graph()
    for _, qg, _ in survey(root):
        if qg is not None:
            g += qg
    return g


@pytest.mark.parametrize("name", sorted([*COMMANDS, *FILE_COMMANDS]))
def test_cmd_output_is_the_cli_output(name, tmp_path, monkeypatch) -> None:
    import json

    # nemik:W232: metrics also asks opa for realizability; this test compares two runs of the same
    # command, so opa is pinned absent for both (both report the queue "unjudged"), and the policy's
    # own verdicts are tested in test_realize.py / test_metrics_realizability.py.
    monkeypatch.setenv("OPA_BIN", "/nonexistent/opa")

    q = tmp_path / "a" / ".claude"
    q.mkdir(parents=True)
    (q / "paths-forward.json").write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": str(tmp_path / "a"),
                "counter": 2,
                "waypoints": [
                    {"symbol": "W1", "title": "t", "status": "ready", "touches": ["x"]},
                    {
                        "symbol": "W2",
                        "title": "u",
                        "status": "blocked",
                        "blocked_on": ["b"],
                        "blocked_kind": "agent",
                        "touches": ["x"],
                    },
                ],
                "residue": [],
            }
        )
    )
    _, argv, _ = {**COMMANDS, **FILE_COMMANDS}[name]
    code, out = run(name, _graph(tmp_path), str(tmp_path), "a")
    mod = {
        "rank": "nemik.rank:main",
        "goals": "nemik.rank:main",
        "rank-check": "nemik.rank:main",
        "overlaps": "nemik.overlaps:main",
        "overlaps-cross": "nemik.overlaps:main",
        "inbound": "nemik.blocks_cli:main",
        "operator": "nemik.blocks_cli:operator_main",
        "wake": "nemik.wake:main",
        "check": "nemik.check:main",
        "metrics": "nemik.metrics:main",
        "floor-asks": "nemik.floorasks:main",
        "witnesses": "nemik.witnesses:main",
    }.get(name, "")
    if name.startswith("pf-"):  # mtools' CLI, pointed at the same queue file
        cli = installed.run(
            "mikemol-paths-forward",
            "--state",
            str(tmp_path / "a" / ".claude" / "paths-forward.json"),
            "--" + name[3:],
        )
        assert (code, out) == (cli.returncode, cli.stdout)
        return
    cli = installed.run(SCRIPTS[mod], *argv("a"), "--root", str(tmp_path))

    def stable(text: str) -> str:
        # nemik:W270: waypoint ages move with the clock, so two runs a second apart differ.
        return "\n".join(
            ln for ln in text.splitlines() if "nemik_waypoint_age_seconds{" not in ln
        )

    assert (code, stable(out)) == (cli.returncode, stable(cli.stdout))


def test_unknown_command_and_bad_repo_are_refused() -> None:
    g = Graph()
    for bad in (("nope", None), ("rank", None), ("rank", "../x"), ("inbound", "a b")):
        with pytest.raises(ValueError):
            run(bad[0], g, "/nonexistent", bad[1])
