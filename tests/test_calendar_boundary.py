"""nemik:W161: operator calendars stay host-side. Event text and the account credential never reach
the graph nemik-serve builds, the metrics, the export or the static build (operator 2026-09-28).

Two witnesses. Structural: no module on the served/exported path imports the calendar reader, at
any depth (the import graph is read from the source, so a new import fails here first). Behavioural:
a queue blocked on cal:<label>/<uid> yields a served document with no event in it.
"""

import ast
from pathlib import Path

import nemik

SRC = Path(nemik.__file__).parent
SERVED = ["serve", "metrics", "check", "manifest", "withheld", "tools", "export"]
# calwrite carries waypoint titles (W197), calendars carries event text (W157).
HOST_ONLY = {"nemik.calendars", "nemik.calwrite"}


def _imports(mod: str) -> set[str]:
    path = SRC / (mod.removeprefix("nemik.").replace(".", "/") + ".py")
    if not path.exists():
        return set()
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("nemik")
        ):
            out.add(node.module)
        elif isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.startswith("nemik")}
    return out


def test_no_served_module_reaches_the_calendar_reader() -> None:
    for start in SERVED:
        seen, stack = set(), [f"nemik.{start}"]
        while stack:
            m = stack.pop()
            if m in seen:
                continue
            seen.add(m)
            stack += sorted(_imports(m))
        assert not seen & HOST_ONLY, f"nemik.{start} reaches {seen & HOST_ONLY}"


def test_a_cal_blocker_serves_no_event(tmp_path) -> None:
    import json

    from nemik.serve import Model

    repo = tmp_path / "life" / ".claude"
    repo.mkdir(parents=True)
    (repo / "paths-forward.json").write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": str(tmp_path / "life"),
                "counter": 1,
                "residue": [],
                "waypoints": [
                    {
                        "symbol": "W1",
                        "title": "after the appointment",
                        "status": "blocked",
                        "blocked_on": ["cal:home/a@t"],
                        "blocked_kind": "agent",
                    }
                ],
            }
        )
    )
    m = Model(tmp_path)
    m.refresh()
    text = json.dumps(m.doc) + m.metrics().decode()
    assert "urn:nemik:cal:" not in text and "Event" not in text
