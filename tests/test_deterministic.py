"""nemik:W119: the served graph is the same bytes whatever Python's str-hash salt is.

The operator saw the web view "jumping around" with no data change. rdflib iterates in hash order,
str hashes are salted per process, and luthen runs two replicas, so each pod (and each restart)
handed the layout the same graph in a different order, and sometimes with a different edge set:
one inbound row per (blocked, blocker) pair survived, chosen by that order.
"""

import json
import subprocess

import installed


def _queue(root, repo, wps):
    d = root / repo / ".claude"
    d.mkdir(parents=True)
    (d / "paths-forward.json").write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": str(root / repo),
                "counter": 9,
                "waypoints": wps,
                "residue": [],
            }
        )
    )


def _wp(sym, status="ready", **kw):
    return {
        "symbol": sym,
        "title": f"item {sym}",
        "status": status,
        "enables": [],
        "blocked_on": [],
        "blocked_kind": None,
        **kw,
    }


def test_graph_json_is_identical_across_hash_seeds(tmp_path) -> None:
    # linux-sources:W40's shape: several blocked_on entries landing on one workstream, one of them
    # its session name, plus peers claiming and not claiming.
    _queue(tmp_path, "tools", [_wp("W24"), _wp("W46"), _wp("W7", enables=["app:W3"])])
    _queue(
        tmp_path,
        "app",
        [
            _wp(
                "W40",
                "blocked",
                blocked_on=["tools-91: port entry point", "tools:W24", "tools:W46"],
                blocked_kind="agent",
            ),
            _wp(
                "W3",
                "blocked",
                blocked_on=["tools", "operator: decide a or b", "W40"],
                blocked_kind="agent",
            ),
            _wp("W5", "blocked", blocked_on=["operator"], blocked_kind="human"),
        ],
    )
    code = (
        "import sys; from pathlib import Path; from nemik.serve import Model; "
        "m = Model(Path(sys.argv[1])); m.refresh(); sys.stdout.buffer.write(m.payload)"
    )
    py = installed._bin()[0] / "python3"
    out = set()
    for seed in ("1", "2", "3", "4"):
        env = {**installed._bin()[1], "PYTHONHASHSEED": seed}
        r = subprocess.run(
            [str(py), "-c", code, str(tmp_path)],
            env=env,
            capture_output=True,
            check=True,
        )
        out.add(r.stdout)
    assert len(out) == 1
