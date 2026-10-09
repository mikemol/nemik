"""nemik:W233: luthen's host-apply export is read, validated, and never taken on trust."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nemik.hostapply import effect_of, fact, load, parse, restarts_of

NOW = "2026-10-09T06:00:00Z"
ROW_OK = {"at": "2026-10-09T05:47:12Z", "digest": "ab" * 32}


def _export(**over: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "version": 1,
        "as_of": "2026-10-09T05:47:12Z",
        "kinds": {
            "bees": {
                "effect": "restart",
                "restarts": [{"unit": "beesd@*.service", "verb": "try-restart"}],
            },
            "drain-tier": {
                "effect": "start-heavy",
                "restarts": [{"unit": "luthen-drain-tier.service", "verb": "start"}],
            },
            "install": {"effect": "install", "restarts": []},
        },
        "rows": [
            {
                "id": "beesd-verbosity",
                "activate": "bees",
                "after": [],
                "applied": ROW_OK,
            },
            {
                "id": "drain-tier-service",
                "activate": "drain-tier",
                "after": [],
                "applied": None,
            },
            {
                "id": "cdi-luthen-tpm",
                "activate": "install",
                "after": [],
                "applied": ROW_OK,
            },
        ],
    }
    doc.update(over)
    return doc


def test_the_real_shape_parses_without_problems() -> None:
    export = parse(_export())
    assert export.problems == ()
    assert sorted(export.rows) == [
        "beesd-verbosity",
        "cdi-luthen-tpm",
        "drain-tier-service",
    ]
    assert export.rows["beesd-verbosity"].applied == (ROW_OK["at"], ROW_OK["digest"])
    assert export.rows["drain-tier-service"].applied is None


def test_an_empty_after_is_ordering_unknown_not_independent() -> None:
    assert parse(_export()).ordering == "none"
    stated = _export(
        rows=[
            {"id": "a", "activate": "install", "after": [], "applied": None},
            {"id": "b", "activate": "install", "after": ["a"], "applied": None},
        ]
    )
    assert parse(stated).ordering == "stated"
    declared = {**stated, "ordering": "none"}
    assert parse(declared).ordering == "none"


def test_a_row_walks_to_its_kind_and_the_units_it_touches() -> None:
    export = parse(_export())
    assert restarts_of(export, "beesd-verbosity") == [
        ("beesd@*.service", "try-restart")
    ]
    assert restarts_of(export, "cdi-luthen-tpm") == []
    assert restarts_of(export, "no-such-row") == []
    assert effect_of(export, "drain-tier-service") == "start-heavy"
    assert effect_of(export, "no-such-row") is None


def test_the_fact_passes_only_for_a_fresh_applied_row() -> None:
    export = parse(_export())
    ok = fact(export, "beesd-verbosity", NOW)
    assert ok is not None and ok["applied"] is True and ok["stale"] is False
    assert ok["digest"] == ROW_OK["digest"]
    unapplied = fact(export, "drain-tier-service", NOW)
    assert unapplied is not None and unapplied["applied"] is False


def test_a_stale_export_proves_nothing() -> None:
    export = parse(_export())
    late = fact(export, "beesd-verbosity", "2026-10-09T09:00:00Z")
    assert late is not None and late["applied"] is False and late["stale"] is True


def test_an_unknown_row_is_an_unresolved_citation_not_a_pass() -> None:
    assert fact(parse(_export()), "home-mount-typo", NOW) is None


def test_a_malformed_export_is_reported_and_never_reads_as_applied() -> None:
    export = parse(
        _export(
            rows=[
                {
                    "id": "x",
                    "activate": "no-such-kind",
                    "after": ["ghost"],
                    "applied": ROW_OK,
                },
                {"id": "x", "activate": "install", "after": [], "applied": ROW_OK},
                {"activate": "install"},
            ]
        )
    )
    assert any("unknown kind" in p for p in export.problems)
    assert any("unknown row ghost" in p for p in export.problems)
    assert any("duplicate id" in p for p in export.problems)
    assert any("no id" in p for p in export.problems)
    flagged = fact(export, "x", NOW)
    assert flagged is not None and flagged["applied"] is False


def test_an_unknown_effect_or_verb_is_a_problem() -> None:
    bad = _export(
        kinds={
            "k": {"effect": "explode", "restarts": [{"unit": "u", "verb": "detonate"}]}
        },
        rows=[],
    )
    problems = parse(bad).problems
    assert any("unknown effect" in p for p in problems)
    assert any("unknown verb" in p for p in problems)


def test_another_version_is_refused() -> None:
    with pytest.raises(ValueError, match="not a host-apply export v1"):
        parse(_export(version=2))


def test_load_reads_the_file_beside_liveness_json(tmp_path: Path) -> None:
    (tmp_path / "host-apply.json").write_text(json.dumps(_export()), encoding="utf-8")
    export = load(tmp_path)
    assert export is not None and "beesd-verbosity" in export.rows


def test_load_finds_nothing_when_there_is_neither_file_nor_exporter(
    tmp_path: Path,
) -> None:
    assert load(tmp_path) is None


def test_load_refuses_a_file_that_is_not_json(tmp_path: Path) -> None:
    (tmp_path / "host-apply.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        load(tmp_path)
