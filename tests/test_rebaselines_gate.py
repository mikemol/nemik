# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2088: the gate refuses a ratchet rise with no declared rebaseline, in a throwaway repo.

HEAD holds foo-baseline.json with one entry. The staged tree is a directory with two. The gate
builds the BEFORE tree from HEAD with git and runs `mikemol-ratchet rebaselines` on the staged tree
against it. An undeclared rise (and a birth at a nonzero value) is refused with status 1, a declared
one is admitted with status 0, and a git failure refuses rather than passes.
"""

from pathlib import Path

import pytest
from mikemol.procrun.proc import capture
from rebaselines_gate import main

BEFORE = '{"a.py": "x"}\n'
AFTER = '{"a.py": "x", "b.py": "y"}\n'
DECLARED = (
    '{"rebaselines": [{"ratchet": "foo-baseline.json", "old": 1, "new": 2, '
    '"reason": "test", "warrant": "695f3e0a-d36f-4080-9c67-7548978cd99e:153941"}]}\n'
)
REFUSED = 1
ADMITTED = 0
UNJUDGED = 7
DECLARES = '{"ratchets": [{"path": "foo-baseline.json", "kind": "baseline"}]}\n'
DECLARES_NOTHING = '{"ratchets": []}\n'
GATE = Path(__file__).resolve().parents[1] / "tools" / "gate_staged.sh"
BIRTH = (
    '{"rebaselines": [{"ratchet": "foo-baseline.json", "old": 0, "new": 2, '
    '"reason": "birth", "warrant": "695f3e0a-d36f-4080-9c67-7548978cd99e:151496"}]}\n'
)
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@t"]


def _git(repo: Path, *args: str) -> str:
    done = capture(["git", "-C", str(repo), *IDENTITY, *args])
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _repo(tmp: Path, committed: dict[str, str]) -> str:
    """Make a repository whose HEAD holds `committed`.

    Returns:
        The HEAD commit.

    """
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for name, text in committed.items():
        (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "head")
    return _git(repo, "rev-parse", "HEAD")


def _run(tmp: Path, head: str, staged: dict[str, str]) -> int:
    tree = tmp / "tree"
    tree.mkdir()
    for name, text in staged.items():
        (tree / name).write_text(text, encoding="utf-8")
    return main(["--root", str(tmp / "repo"), "--head", head, "--tree", str(tree)])


def test_an_undeclared_rise_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One entry became two and nothing declares it."""
    head = _repo(tmp_path, {"foo-baseline.json": BEFORE})
    assert _run(tmp_path, head, {"foo-baseline.json": AFTER}) == REFUSED
    assert "rose 1 to 2" in capsys.readouterr().out


def test_a_declared_rise_is_admitted(tmp_path: Path) -> None:
    """The same rise with its rebaselines.json entry passes, with status 0."""
    head = _repo(tmp_path, {"foo-baseline.json": BEFORE})
    staged = {"foo-baseline.json": AFTER, "rebaselines.json": DECLARED}
    assert _run(tmp_path, head, staged) == ADMITTED


def test_a_fall_needs_no_entry(tmp_path: Path) -> None:
    """Paydown is what a ratchet is for."""
    head = _repo(tmp_path, {"foo-baseline.json": AFTER})
    assert _run(tmp_path, head, {"foo-baseline.json": BEFORE}) == ADMITTED


def test_a_birth_at_a_nonzero_value_is_a_rise_from_nothing(tmp_path: Path) -> None:
    """HEAD has no such file, so two entries are a rise of two and need a declaration."""
    head = _repo(tmp_path, {"README": "x\n"})
    assert _run(tmp_path, head, {"foo-baseline.json": AFTER}) == REFUSED


def test_a_git_failure_refuses_rather_than_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown commit cannot be compared with, so the gate refuses."""
    _repo(tmp_path, {"foo-baseline.json": BEFORE})
    assert _run(tmp_path, "0" * 40, {"foo-baseline.json": BEFORE}) == UNJUDGED
    out = capsys.readouterr().out
    assert "could not judge" in out
    assert "git ls-tree failed" in out


def test_retiring_a_declaration_does_not_hide_a_rise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stage that drops the declared row and raises the file is refused (B1)."""
    head = _repo(tmp_path, {"foo-baseline.json": BEFORE, "ratchets.json": DECLARES})
    staged = {"foo-baseline.json": AFTER, "ratchets.json": DECLARES_NOTHING}
    assert _run(tmp_path, head, staged) == REFUSED
    assert "no longer declared" in capsys.readouterr().out


def test_an_unreadable_staged_value_is_not_judged_as_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A corrupt staged ratchet file is could-not-judge, status 7 (B2)."""
    head = _repo(tmp_path, {"foo-baseline.json": BEFORE, "ratchets.json": DECLARES})
    staged = {"foo-baseline.json": "{not json", "ratchets.json": DECLARES}
    assert _run(tmp_path, head, staged) == UNJUDGED
    assert "unreadable value" in capsys.readouterr().out


def test_the_gate_script_runs_this_check_after_the_pycheck_step() -> None:
    """Removing the step from tools/gate_staged.sh fails this test."""
    text = GATE.read_text(encoding="utf-8")
    step = text.index("tools/rebaselines_gate.py")
    assert text.index("mikemol-pycheck --ratchet") < step
    assert "commit refused" in text[step:]


def test_a_new_ratchet_file_is_admitted_with_its_birth_entry(tmp_path: Path) -> None:
    """The W2077 case: a file absent at HEAD, old 0, is admitted with an entry and not without."""
    head = _repo(tmp_path, {"README": "x\n"})
    staged = {"foo-baseline.json": AFTER, "rebaselines.json": BIRTH}
    assert _run(tmp_path, head, staged) == ADMITTED


EMPTY = "{}\n"
ONE_FINDING = '{"a.py": {"E501": 1}}\n'
COUNTS = (
    '{"ratchets": [{"path": "foo-baseline.json", "kind": "baseline",'
    ' "expression": "file_rule_count"}]}\n'
)
FROM_ZERO = (
    '{"rebaselines": [{"ratchet": "foo-baseline.json", "old": 0, "new": 1, '
    '"reason": "test", "warrant": "695f3e0a-d36f-4080-9c67-7548978cd99e:153941"}]}\n'
)


def test_an_empty_baseline_is_a_count_of_zero_not_unread(tmp_path: Path) -> None:
    """The W2115 case: nemik's ruff and mypy baselines are {}, which the census reads as None."""
    head = _repo(tmp_path, {"foo-baseline.json": EMPTY, "ratchets.json": COUNTS})
    staged = {"foo-baseline.json": EMPTY, "ratchets.json": COUNTS}
    assert _run(tmp_path, head, staged) == ADMITTED


def test_a_rise_out_of_an_empty_baseline_is_refused_without_an_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Zero to one finding is a rise: reading {} as unread would have skipped it."""
    head = _repo(tmp_path, {"foo-baseline.json": EMPTY, "ratchets.json": COUNTS})
    staged = {"foo-baseline.json": ONE_FINDING, "ratchets.json": COUNTS}
    assert _run(tmp_path, head, staged) == REFUSED
    assert "rose 0 to 1" in capsys.readouterr().out


def test_a_rise_out_of_an_empty_baseline_is_admitted_with_its_entry(
    tmp_path: Path,
) -> None:
    """The same rise declared from 0 to 1 passes."""
    head = _repo(tmp_path, {"foo-baseline.json": EMPTY, "ratchets.json": COUNTS})
    staged = {
        "foo-baseline.json": ONE_FINDING,
        "ratchets.json": COUNTS,
        "rebaselines.json": FROM_ZERO,
    }
    assert _run(tmp_path, head, staged) == ADMITTED


@pytest.mark.parametrize("broken", ["{not json", '{"a.py": {}}\n'])
def test_a_malformed_baseline_is_still_unread_where_an_empty_one_is_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], broken: str
) -> None:
    """Only exactly {} is zero: a broken file and a hollow entry stay could-not-judge."""
    head = _repo(tmp_path, {"foo-baseline.json": EMPTY, "ratchets.json": COUNTS})
    staged = {"foo-baseline.json": broken, "ratchets.json": COUNTS}
    assert _run(tmp_path, head, staged) == UNJUDGED
    assert "unreadable value" in capsys.readouterr().out
