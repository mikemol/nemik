import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.check import survey
from nemik.tools import COMMANDS, FILE_COMMANDS, run



def _graph(root: Path) -> Graph:
    g = Graph()
    for _, qg, _ in survey(root):
        if qg is not None:
            g += qg
    return g


@pytest.mark.parametrize("name", sorted([*COMMANDS, *FILE_COMMANDS]))
def test_cmd_output_is_the_cli_output(name, tmp_path) -> None:
    import json

    q = tmp_path / "a" / ".claude"
    q.mkdir(parents=True)
    (q / "paths-forward.json").write_text(json.dumps({"version": 1, "project_root": str(tmp_path / "a"), "counter": 2,
        "waypoints": [{"symbol": "W1", "title": "t", "status": "ready", "touches": ["x"]},
                      {"symbol": "W2", "title": "u", "status": "blocked", "blocked_on": ["b"], "blocked_kind": "agent",
                       "touches": ["x"]}], "residue": []}))
    fn, argv, _ = {**COMMANDS, **FILE_COMMANDS}[name]
    code, out = run(name, _graph(tmp_path), str(tmp_path), "a")
    mod = {"rank": "nemik.rank:main", "goals": "nemik.rank:main", "rank-check": "nemik.rank:main",
                    "overlaps": "nemik.overlaps:main", "overlaps-cross": "nemik.overlaps:main",
                    "inbound": "nemik.blocks:main", "operator": "nemik.blocks:operator_main",
                    "wake": "nemik.wake:main", "check": "nemik.check:main", "metrics": "nemik.metrics:main",
                    "floor-asks": "nemik.floorasks:main", "witnesses": "nemik.witnesses:main"}.get(name, "")
    if name.startswith("pf-"):  # mtools' CLI, pointed at the same queue file
        cli = subprocess.run([str(Path(sys.executable).parent / "mikemol-paths-forward"), "--state",
                              str(tmp_path / "a" / ".claude" / "paths-forward.json"), "--" + name[3:]],
                             capture_output=True, text=True)
        assert (code, out) == (cli.returncode, cli.stdout)
        return
    mod, _, attr = mod.partition(":")
    cli = subprocess.run([sys.executable, "-c", f"import sys; from {mod} import {attr}; {attr}(sys.argv[1:])",
                          *argv("a"), "--root", str(tmp_path)], capture_output=True, text=True)
    assert (code, out) == (cli.returncode, cli.stdout)


def test_unknown_command_and_bad_repo_are_refused() -> None:
    g = Graph()
    for bad in (("nope", None), ("rank", None), ("rank", "../x"), ("inbound", "a b")):
        with pytest.raises(ValueError):
            run(bad[0], g, "/nonexistent", bad[1])
