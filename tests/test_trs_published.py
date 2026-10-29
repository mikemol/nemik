# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W449: the static build publishes each repo's TRS as Turtle, minus any withheld card."""

import json
from pathlib import Path

from rdflib import Graph, URIRef

from nemik.serve import build_static
from nemik.trs import LDP, TRS

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _build(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    withheld = tmp_path / "withheld.json"
    payload: dict[str, object] = {"version": 1, "as_of": "x", "items": items}
    withheld.write_text(json.dumps(payload))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    return out


def test_every_repo_has_a_parsable_base_and_change_log(tmp_path: Path) -> None:
    out = _build(tmp_path, [])
    repos = sorted(p.name for p in (out / "trs").iterdir())
    assert repos
    for repo in repos:
        base = Graph().parse(out / "trs" / repo / "base.ttl", format="turtle")
        log = Graph().parse(out / "trs" / repo / "changelog.ttl", format="turtle")
        assert set(base.subjects(None, TRS.Base))
        assert set(log.subjects(None, TRS.ChangeLog))
    assert any(
        set(
            Graph()
            .parse(out / "trs" / r / "base.ttl", format="turtle")
            .objects(None, LDP.member)
        )
        for r in repos
    )


def test_a_withheld_card_is_in_neither_the_base_nor_the_log(tmp_path: Path) -> None:
    first = _build(tmp_path / "a", [])
    repo = min(p.name for p in (first / "trs").iterdir())
    base = Graph().parse(first / "trs" / repo / "base.ttl", format="turtle")
    card = min(base.objects(None, LDP.member), key=str)
    cite = str(card).removeprefix("urn:nemik:").replace("/", ":", 1)
    hidden = _build(tmp_path / "b", [{"ref": cite, "reason": "test"}])
    for part in ("base", "changelog"):
        text = (hidden / "trs" / repo / f"{part}.ttl").read_text()
        g = Graph().parse(data=text, format="turtle")
        assert (None, None, URIRef(str(card))) not in g, (part, cite)
