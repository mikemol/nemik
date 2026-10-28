# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
import json
from pathlib import Path

from nemik.floorasks import floor_asks, unresolved

BIB = """@misc{a1,
  title = {x},
  waypoint = {r:W1}
}
@misc{a2,
  waypoint = {r:W2}
}
@misc{a3,
  waypoint = {r:W9}
}
@misc{a4,
  waypoint = {ghost:W1}
}
@misc{a5,
  waypoint = {r}
}
@misc{a6,
  title = {no pointer}
}
"""


def test_each_bad_pointer_is_named(tmp_path: Path) -> None:
    (tmp_path / "r" / ".claude").mkdir(parents=True)
    payload: dict[str, object] = {
        "waypoints": [{"symbol": "W1", "status": "done"}],
        "residue": [{"symbol": "W2"}],
    }
    (tmp_path / "r" / ".claude" / "paths-forward.json").write_text(json.dumps(payload))
    floor = tmp_path / "floor"
    floor.mkdir()
    (floor / "asks.bib").write_text(BIB)
    assert len(floor_asks(floor)) == 5
    assert {(k, why) for k, _, why in unresolved(tmp_path, floor)} == {
        ("a2", "dropped"),
        ("a3", "no such waypoint"),
        ("a4", "no queue for repo"),
        ("a5", "malformed"),
    }
