# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1096: a one-shot build keeps no parsed graphs, so none is held beside the copy it uses."""

from pathlib import Path

import pytest

from nemik import adapter

LEDGER = '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "one"\n'


def test_the_cache_holds_a_graph_until_a_build_forgets_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A long-lived reader keeps the parsed graph; forget_parsed drops it and keeps none after."""
    monkeypatch.setattr(adapter, "_KEEP", [True])
    monkeypatch.setattr(adapter, "_PARSED", {})
    path = tmp_path / "ledger"
    path.write_text(LEDGER, encoding="utf-8")
    kept, _ = adapter.ledger_graph("a", path)
    assert adapter.parsed_count() == 1
    adapter.forget_parsed()
    assert adapter.parsed_count() == 0
    forgotten, _ = adapter.ledger_graph("a", path)
    assert adapter.parsed_count() == 0
    assert len(forgotten) == len(kept)
