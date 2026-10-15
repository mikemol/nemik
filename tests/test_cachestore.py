# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W518: the build's caches survive a process boundary, and only ever when they are still valid."""

from pathlib import Path

import pytest
from rdflib import Graph

from nemik import cachestore, flow, shaclinc
from nemik.serve import Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _forget() -> None:
    shaclinc._LAST.clear()
    flow._SOLVES.clear()


@pytest.fixture(autouse=True)
def _clean_caches() -> None:
    _forget()


def _build() -> Model:
    model = Model(FLEET, frozenset())
    model.refresh()
    return model


def test_a_saved_cache_is_restored_exactly(tmp_path: Path) -> None:
    _build()
    held, solves = shaclinc.export_cache(), flow.export_solves()
    assert held and solves, "the build left nothing to keep"
    assert cachestore.save(tmp_path) > 0
    _forget()
    assert cachestore.load(tmp_path) is True
    assert shaclinc.export_cache() == held
    assert flow.export_solves() == solves


def test_a_restored_cache_makes_an_unchanged_rebuild_validate_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the reason this exists: a fresh process rebuilding cold validates the whole fleet
    runs: list[int] = []
    real = shaclinc._results

    def counting(data: Graph, shapes: Graph) -> dict:
        runs.append(len(data))
        return real(data, shapes)

    monkeypatch.setattr(shaclinc, "_results", counting)
    _build()
    cold = len(runs)
    assert cold >= 1
    cachestore.save(tmp_path)
    _forget()
    runs.clear()
    assert cachestore.load(tmp_path)
    again = _build()
    assert runs == [], "a restored cache still validated the fleet again"
    assert again.nodes > 0


def test_a_cache_computed_by_other_code_is_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build()
    cachestore.save(tmp_path)
    _forget()
    monkeypatch.setattr(cachestore, "stamp", lambda: "the shapes changed")
    assert cachestore.load(tmp_path) is False
    assert not shaclinc.export_cache() and not flow.export_solves()


def test_a_missing_or_damaged_file_is_a_cold_start(tmp_path: Path) -> None:
    assert cachestore.load(tmp_path) is False
    (tmp_path / cachestore.NAME).write_bytes(b"not a pickle")
    assert cachestore.load(tmp_path) is False
    (tmp_path / cachestore.NAME).write_bytes(b"")
    assert cachestore.load(tmp_path) is False
    assert not shaclinc.export_cache() and not flow.export_solves()


def test_the_stamp_follows_the_shapes() -> None:
    assert cachestore.stamp() == cachestore.stamp()
    assert len(cachestore.stamp()) == 64
