# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2263: a witness reading a field no observer produces is named, and the table is true."""

import os
from pathlib import Path

import pytest
from queue_cases import make_card, write_queue

from nemik import witnesses
from nemik.check import shapes
from nemik.shaclinc import shacl_results
from nemik.witnessreads import FIELDS, unknown

HERE = Path(__file__).parent
NAMED = "this card's witness reads "


def test_the_hand_written_git_ref_form_is_unknown_and_the_real_one_is_not() -> None:
    """`resolves` is not a git_ref field (the nine landed cards); `exists` and `sha` are."""
    assert unknown('input.git_ref["nemik@abc"].resolves == true') == [
        "git_ref.resolves"
    ]
    assert unknown('input.git_ref["nemik@abc"].exists == true') == []
    assert unknown('input.git_ref["nemik@abc"].sha != ""') == []


def test_an_unknown_observer_and_a_whole_fact_read() -> None:
    """A made-up observer is named alone, a whole-fact read is fine, and a name appears once."""
    assert unknown('input.volume["data"].free > 1') == ["volume"]
    assert unknown('count(input.pid["localhost/1"]) > 0') == []
    both = 'input.file["a"].mtime > 1 and input.file["b"].mtime > 2'
    assert unknown(both) == ["file.mtime"]
    assert unknown("") == []


def test_the_field_table_matches_the_observers_that_run_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """file, git_ref and pid answer exactly the fields the table lists."""
    (tmp_path / "nemik" / ".git").mkdir(parents=True)
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    file_fact = witnesses.OBSERVERS["file"](str(HERE))
    ref_fact = witnesses.OBSERVERS["git_ref"]("nemik@HEAD")
    pid_fact = witnesses.OBSERVERS["pid"](f"localhost/{os.getpid()}")
    assert file_fact is not None
    assert ref_fact is not None
    assert pid_fact is not None
    assert sorted(file_fact) == sorted(FIELDS["file"])
    assert sorted(pid_fact) == sorted(FIELDS["pid"])
    assert sorted(ref_fact) == sorted(FIELDS["git_ref"])
    assert sorted(FIELDS) == sorted(witnesses.OBSERVERS)


def test_a_card_with_an_unknown_field_draws_the_warning_naming_it(
    tmp_path: Path,
) -> None:
    """The adapter keeps the name, the shape warns with it, and a good witness draws nothing."""
    bad = make_card("W1", "landed", [], [])
    bad["witness"] = 'input.git_ref["nemik@abc"].resolves == true'
    good = make_card("W2", "landed", [], [])
    good["witness"] = 'input.git_ref["nemik@abc"].exists == true'
    g = write_queue(tmp_path / "alpha.json", "alpha", [bad, good])
    found = {
        str(focus): m
        for focus, rows in shacl_results(g, shapes()).items()
        for _, m, _ in rows
        if m.startswith(NAMED)
    }
    assert list(found) == ["urn:nemik:alpha/W1"]
    assert "git_ref.resolves" in found["urn:nemik:alpha/W1"]
