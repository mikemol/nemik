# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik.endpoint and nemik.witnesses_cli: backends found without a hand-set environment (W227)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from nemik import endpoint, witnesses, witnesses_cli

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ANSWER = (
    '{"state": "answered", "name": "vmsingle-http", "side": "host",'
    ' "address": "vmsingle.example.test:8428"}'
)


def stub_luthen(root: Path, printed: str, code: int = 0) -> None:
    """Lay out a luthen-observability checkout whose endpoints_query prints `printed`."""
    checks = root / endpoint.LUTHEN / "checks"
    checks.mkdir(parents=True)
    (checks / "__init__.py").write_text("")
    script = f"import sys\nsys.stdout.write({printed!r})\nsys.exit({code})\n"
    (checks / "endpoints_query.py").write_text(script)


def clear(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Point NEMIK_ROOT at `root` and unset both backend variables."""
    monkeypatch.setenv("NEMIK_ROOT", str(root))
    for env in endpoint.PORT_NAMES:
        monkeypatch.delenv(env, raising=False)


def test_unset_variables_come_from_luthens_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_luthen(tmp_path, ANSWER)
    clear(monkeypatch, tmp_path)
    assert sorted(endpoint.export_defaults()) == ["NEMIK_VMALERT_URL", "NEMIK_VM_URL"]
    assert os.environ["NEMIK_VM_URL"] == "http://vmsingle.example.test:8428"


def test_the_environment_wins_over_the_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_luthen(tmp_path, ANSWER)
    clear(monkeypatch, tmp_path)
    monkeypatch.setenv("NEMIK_VM_URL", "http://override.test:1")
    assert endpoint.export_defaults() == ["NEMIK_VMALERT_URL"]
    assert os.environ["NEMIK_VM_URL"] == "http://override.test:1"


def test_no_checkout_leaves_the_variables_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear(monkeypatch, tmp_path)
    assert endpoint.export_defaults() == []
    assert "NEMIK_VM_URL" not in os.environ


def test_an_unanswered_tool_gives_no_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_luthen(tmp_path, '{"state": "unknown", "name": "vmsingle-http"}')
    clear(monkeypatch, tmp_path)
    assert endpoint.declared_base("vmsingle-http", tmp_path) is None
    assert endpoint.export_defaults() == []


def test_the_tool_exiting_nonzero_gives_no_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_luthen(tmp_path, ANSWER, code=2)
    clear(monkeypatch, tmp_path)
    assert endpoint.declared_base("vmsingle-http", tmp_path) is None


def test_the_entry_point_exports_then_runs_witnesses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_luthen(tmp_path, ANSWER)
    clear(monkeypatch, tmp_path)
    seen: list[str] = []

    def fake_main(argv: list[str] | None = None) -> None:
        seen.append(os.environ.get("NEMIK_VM_URL", "unset"))
        seen.extend(argv or [])

    monkeypatch.setattr(witnesses, "main", fake_main)
    witnesses_cli.main(["--apply"])
    assert seen == ["http://vmsingle.example.test:8428", "--apply"]
