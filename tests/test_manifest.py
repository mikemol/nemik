"""nemik:W154: the field manifest covers every field the export renders, and flags any that is new."""

from pathlib import Path

from nemik.manifest import load, unmanifested
from nemik.rank import goals, load_weights
from nemik.serve import Model
from nemik.wake import operator_row, read_liveness, roster

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _documents():
    m = Model(FLEET)
    m.refresh()
    live, source = read_liveness(FLEET, None)
    yield "graph.json", m.doc
    yield "wake.json", {"liveness": source, "roster": roster(m.graph, live), "operator": operator_row(m.graph)}
    for repo in sorted({n["repo"] for n in m.doc["nodes"]}):
        yield f"goals/{repo}.json", goals(m.graph, repo, load_weights())


def test_every_rendered_field_is_manifested() -> None:
    for name, doc in _documents():
        assert unmanifested(name, doc) == [], name


def test_a_new_field_is_flagged() -> None:
    docs = dict(_documents())
    docs["graph.json"]["nodes"][0]["secret"] = "x"
    assert unmanifested("graph.json", docs["graph.json"]) == ["graph.json nodes.secret"]
    assert unmanifested("goals/x.json", [{"goal": "W1", "leak": 1}]) == ["goals/x.json goals.leak"]
    assert unmanifested("extra.json", {}) == ["extra.json: file is not in the manifest"]


def test_manifest_classes_are_known() -> None:
    known = {"ref", "enum", "count", "flag", "time", "text", "counts", "records", "record", "list-ref", "list-text", "list-time"}
    for spec in load().values():
        for fields in spec.values():
            assert set(fields.values()) <= known
