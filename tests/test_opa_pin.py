# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W535: witnesses resolve opa through pathsforward's pin, so a stray opa decides nothing."""

from pathlib import Path

import pytest

from nemik.witnesses import evaluate


def test_an_opa_that_is_not_the_pinned_version_is_undefined(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The fake opa reports another version: the query is undefined, never a pass."""
    fake = tmp_path / "opa"
    fake.write_text("#!/bin/sh\necho 'Version: 0.0.1'\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("NEMIK_OPA", str(fake))
    doc: dict[str, object] = {"now": "2026-10-17T00:00:00+00:00"}
    assert evaluate("input.now", doc, []) == "undefined"


def test_a_missing_fact_is_undefined_before_opa_is_asked() -> None:
    """The shared rule: an unobservable fact is undefined, whatever opa would say."""
    doc: dict[str, object] = {}
    assert evaluate('input.pid["1"].alive', doc, ['pid["1"]']) == "undefined"
