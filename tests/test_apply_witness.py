"""nemik:W233: `input.apply["<row id>"]` is a witness fact from luthen's host-apply export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik.witnesses import facts

QUERY = 'input.apply["home-mount"].applied == true'


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _export(root: Path, as_of: str, applied: bool) -> None:
    mark = {"at": as_of, "digest": "cd" * 32} if applied else None
    row: dict[str, object] = {
        "id": "home-mount",
        "activate": "reload",
        "after": [],
        "applied": mark,
    }
    doc = {
        "version": 1,
        "as_of": as_of,
        "kinds": {"reload": {"effect": "reload", "restarts": []}},
        "rows": [row],
    }
    (root / "host-apply.json").write_text(json.dumps(doc), encoding="utf-8")


def test_a_fresh_applied_row_is_a_true_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    _export(tmp_path, _now(), True)
    doc, missing = facts(QUERY)
    assert missing == []
    assert doc["apply"]["home-mount"]["applied"] is True


def test_an_unapplied_row_is_false_not_undefined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    _export(tmp_path, _now(), False)
    doc, missing = facts(QUERY)
    assert missing == []
    assert doc["apply"]["home-mount"]["applied"] is False


def test_a_stale_export_is_never_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    _export(tmp_path, "2026-01-01T00:00:00Z", True)
    doc, _ = facts(QUERY)
    assert doc["apply"]["home-mount"]["applied"] is False
    assert doc["apply"]["home-mount"]["stale"] is True


def test_a_row_the_export_does_not_hold_is_undefined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    _export(tmp_path, _now(), True)
    _, missing = facts('input.apply["no-such-row"].applied == true')
    assert missing == ['apply["no-such-row"]']


def test_a_row_the_exporter_could_not_read_is_undefined_not_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    row: dict[str, object] = {
        "id": "kubelet-swap",
        "activate": "reload",
        "after": [],
        "applied": None,
        "unobservable": True,
    }
    doc = {
        "version": 1,
        "as_of": _now(),
        "kinds": {"reload": {"effect": "reload", "restarts": []}},
        "rows": [row],
    }
    (tmp_path / "host-apply.json").write_text(json.dumps(doc), encoding="utf-8")
    _, missing = facts('input.apply["kubelet-swap"].applied == true')
    assert missing == ['apply["kubelet-swap"]']


def test_no_export_at_all_is_undefined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    _, missing = facts(QUERY)
    assert missing == ['apply["home-mount"]']
