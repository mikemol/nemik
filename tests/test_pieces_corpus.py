"""nemik:W423: the Python half of the pieces conformance run (the TypeScript half is mtools:W1072).

Every case in tests/corpus/pieces is run through nemik.pieces; any difference is printed field by
field, the report github-8f asked for, rather than a bare pass or fail.
"""

import json
from pathlib import Path

import pytest

from nemik.pieces import assemble, split

CORPUS = Path(__file__).parent / "corpus" / "pieces"
CASES = sorted(CORPUS.glob("*.json"))


def _diff(path: str, want: object, got: object) -> list[str]:
    if isinstance(want, dict) and isinstance(got, dict):
        out: list[str] = []
        for k in sorted(set(want) | set(got)):
            if k not in got:
                out.append(f"{path}.{k}: missing")
            elif k not in want:
                out.append(f"{path}.{k}: unexpected")
            else:
                out += _diff(f"{path}.{k}", want[k], got[k])
        return out
    if isinstance(want, list) and isinstance(got, list) and len(want) == len(got):
        return [
            d
            for i, (a, b) in enumerate(zip(want, got, strict=True))
            for d in _diff(f"{path}[{i}]", a, b)
        ]
    return [] if want == got else [f"{path}: want {want!r}, got {got!r}"]


def test_the_corpus_is_there() -> None:
    assert len(CASES) >= 5


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.stem)
def test_python_agrees_with_the_corpus(case: Path) -> None:
    c = json.loads(case.read_text())
    got_split = json.loads(json.dumps(split(c["doc"]), default=str))
    got_back = json.loads(json.dumps(assemble(got_split), default=str))
    diffs = _diff("split", c["split"], got_split) + _diff(
        "assemble", c["assemble"], got_back
    )
    assert not diffs, "\n".join(diffs)


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.stem)
def test_split_then_assemble_is_identity(case: Path) -> None:
    c = json.loads(case.read_text())
    doc = dict(c["doc"])
    # assemble's canonical order: nodes by id, edges by (source, target, kind)
    doc["nodes"] = sorted(doc["nodes"], key=lambda n: n["id"])
    doc["edges"] = sorted(
        doc["edges"], key=lambda e: (e["source"], e["target"], e["kind"])
    )
    for section in ("findings", "health"):
        doc[section] = dict(sorted(doc[section].items()))
    assert c["assemble"] == doc
