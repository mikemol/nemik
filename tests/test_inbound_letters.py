"""nemik:W275: a waiting waypoint's cited letter files reach nemik-inbound, not the served graph."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import RDF, Graph, Literal

from nemik.adapter import (
    NEMIK,
    OSLC_CM,
    STATE,
    queue_graph,
    waypoint_uri,
    workstream_uri,
)
from nemik.blocks import inbound


def test_the_adapter_reads_letter_paths_from_evidence_and_the_next_step(
    tmp_path: Path,
) -> None:
    path = tmp_path / "q.json"
    waypoint = {
        "symbol": "W1",
        "title": "t",
        "status": "ready",
        "evidence": "2026-10-10: Letter: nemik/inbox/2026-10-09-a-letter.md items 1-2; also "
        ".claude/letters/W1-note.md and a bare inbox word",
        "next_bounded_step": "read life/inbox/2026-10-09-x.md then act",
    }
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 1,
                "residue": [],
                "waypoints": [waypoint],
            }
        )
    )
    g = queue_graph("a", path)
    found = {str(o) for o in g.objects(waypoint_uri("a", "W1"), NEMIK.letter)}
    assert found == {
        "nemik/inbox/2026-10-09-a-letter.md",
        ".claude/letters/W1-note.md",
        "life/inbox/2026-10-09-x.md",
    }


def test_inbound_carries_the_letters_only_when_asked() -> None:
    g = Graph()
    g.add((workstream_uri("b"), RDF.type, NEMIK.Workstream))
    waiter = waypoint_uri("a", "W9")
    g.add((waiter, OSLC_CM.state, STATE["blocked"]))
    g.add((waiter, NEMIK.waitsFor, workstream_uri("b")))
    g.add((waiter, NEMIK.letter, Literal("b/inbox/2026-10-10-ask.md")))
    (plain,) = inbound(g)
    (with_letters,) = inbound(g, letters=True)
    assert "letters" not in plain
    assert with_letters["letters"] == ["b/inbox/2026-10-10-ask.md"]
