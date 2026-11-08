# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2080: the build cache is bounded, so a stale or oversized file cannot keep the pod down.

The pod's builder was OOM-killed on every start because /srv/.cache/build-caches.json had grown to
193 MB (flow solves of graph versions long gone) and load() parsed all of it before comparing the
stamp. The file is now refused by size, refused by the stamp in its first bytes before it is parsed,
and written with only the solves the build used.
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from nemik import cachestore, flow

OTHER_STAMP = "0" * cachestore.STAMP_LEN
STALE_KEY: flow.SolveKey = ((), (), (), (), Fraction(1))
ONE_SOLVE = 1
TWO_SOLVES = 2


def _refuse_to_parse(directory: Path, name: str) -> dict[str, object]:
    """Stand in for the JSON parse and fail the test if load reaches it.

    Raises:
        AssertionError: always, because the file should never have been parsed.

    """
    msg = f"{directory / name} was parsed"
    raise AssertionError(msg)


def test_a_file_over_the_cap_is_a_cold_start_and_is_not_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file larger than the cap is not read into memory at all."""
    monkeypatch.setattr(cachestore, "MAX_BYTES", 100)
    monkeypatch.setattr(cachestore, "_blob", _refuse_to_parse)
    body = {"stamp": cachestore.stamp(), "pad": "x" * 400}
    (tmp_path / cachestore.NAME).write_text(json.dumps(body, separators=(",", ":")))
    assert not cachestore.load(tmp_path)


def test_a_file_with_another_stamp_is_a_cold_start_and_is_not_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stamp is read from the first bytes, so a stale file costs a few bytes, not a parse."""
    monkeypatch.setattr(cachestore, "_blob", _refuse_to_parse)
    body = {"stamp": OTHER_STAMP, "shaclinc": {}, "flow": ["D", []], "terms": []}
    (tmp_path / cachestore.NAME).write_text(json.dumps(body, separators=(",", ":")))
    assert not cachestore.load(tmp_path)


def test_a_file_with_this_stamp_under_the_cap_is_still_restored(tmp_path: Path) -> None:
    """The guards do not turn a good cache into a cold start."""
    body = {
        "stamp": cachestore.stamp(),
        "shaclinc": {},
        "flow": ["D", []],
        "terms": [],
    }
    (tmp_path / cachestore.NAME).write_text(json.dumps(body, separators=(",", ":")))
    flow.reset_solves()
    assert cachestore.load(tmp_path)


def test_a_saved_file_starts_with_the_stamp_the_peek_reads(tmp_path: Path) -> None:
    """save() writes the stamp first, which is what _worth_parsing relies on."""
    flow.reset_solves()
    cachestore.save(tmp_path)
    head = (tmp_path / cachestore.NAME).read_bytes()[: len(cachestore.STAMP_HEAD)]
    assert head == cachestore.STAMP_HEAD


def test_only_the_solves_a_build_used_are_exported() -> None:
    """A restored solve nobody asked for belongs to a graph that is gone, so it is not kept."""
    flow.reset_solves()
    stale = flow.Flow(salience={}, fibre={}, stranded={}, potential={}, current={})
    flow.import_solves({STALE_KEY: stale})
    flow.solve({"a": Fraction(1)}, {"a": ["b"]}, ["b"])
    assert len(flow.export_solves()) == TWO_SOLVES
    used = flow.export_used_solves()
    assert len(used) == ONE_SOLVE
    assert STALE_KEY not in used


def test_a_save_after_a_restore_drops_the_unused_solves(tmp_path: Path) -> None:
    """The file does not grow by the solves of every earlier graph: the cache heals itself."""
    flow.reset_solves()
    stale = flow.Flow(salience={}, fibre={}, stranded={}, potential={}, current={})
    flow.import_solves({STALE_KEY: stale})
    flow.solve({"a": Fraction(1)}, {"a": ["b"]}, ["b"])
    cachestore.save(tmp_path)
    flow.reset_solves()
    assert cachestore.load(tmp_path)
    assert len(flow.export_solves()) == ONE_SOLVE
