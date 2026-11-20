# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2345: the gate's git-fed judgments write JSON verdicts; the gate reads the state."""

import sys
import tempfile
from pathlib import Path

import pytest
from gate_verdict import (
    KINDS,
    CannotJudge,
    Judged,
    State,
    Verdict,
    VerdictError,
    exit_status,
    judge,
    judged,
    parse_verdict,
    read_dir,
    verdict_text,
)
from hook_facts import NO_WORKING_CARD
from mikemol.procrun.proc import capture
from nemik_src import SRC_SPEC, TESTS_SPEC, render

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gate_verdict.py"
GATE = ROOT / "tools" / "gate_staged.sh"
TREE = "a" * 40
OTHER = "b" * 40
HEAD = "c" * 40
MODULES = ["src/nemik/__init__.py", "src/nemik/a.py"]
TESTS = ["tests/test_a.py", "tests/conftest.py"]
SRC_LIST = render(MODULES, SRC_SPEC)
TESTS_LIST = render(TESTS, TESTS_SPEC)
PATHS = "".join(f"{path}\n" for path in MODULES + TESTS)
STAMPS = f"tree {TREE}\nhead {HEAD}\n"
TRACKED = f"facts tracked\n{STAMPS}{PATHS}"
CHANGED = f"facts changed\n{STAMPS}tests/test_a.py\n"
READY = '{"waypoints": [{"symbol": "W1", "status": "ready"}]}'
WORKING = '{"waypoints": [{"status": "ready"}, {"status": "working"}]}'
WHEEL = "vendor/wheels/x-1-py3-none-any.whl"
PYPROJECT = f'wheels = ["{WHEEL}"]'
UNREAD = 7
NONE: list[str] = []
UNKNOWN_STATE = '{"state": "fine", "why": ["x"]}'


def _ok(tree: str = TREE, head: str = HEAD) -> Judged:
    return judged(NONE, tree, head)


def _run(kind: str, *texts: str) -> Verdict:
    """Run a judgment over texts written to files, the way the build action reads them.

    Returns:
        The verdict the judgment made.

    """
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for number, text in enumerate(texts):
            path = Path(tmp) / f"in{number}"
            path.write_text(text, encoding="utf-8")
            files.append(path)
        return judge(kind, files)


def _write(directory: Path, kind: str, text: str) -> None:
    (directory / f"{kind}.json").write_text(text, encoding="utf-8")


def _all_ok(directory: Path, tree: str = TREE, head: str = HEAD) -> None:
    for kind in KINDS:
        _write(directory, kind, verdict_text(_ok(tree, head)))


def _status(directory: Path, tree: str = TREE, head: str = HEAD) -> int:
    argv = [sys.executable, str(TOOL), "status", str(directory), tree, head]
    return capture(argv).returncode


def _judged_raw(
    state: str = "ok",
    problems: str = "[]",
    tree: str = f'"{TREE}"',
    head: str = f'"{HEAD}"',
    extra: str = "",
) -> str:
    """Write a judged verdict as raw JSON text, so a field can be given the wrong shape.

    Returns:
        The text; the defaults are a well-formed ok verdict.

    """
    return f'{{"state": "{state}", "problems": {problems}, "tree": {tree}, "head": {head}{extra}}}'


def _cannot_raw(why: str = '["x"]', extra: str = "") -> str:
    """Write a cannot_judge verdict as raw JSON text.

    Returns:
        The text; the defaults are a well-formed verdict.

    """
    return f'{{"state": "cannot_judge", "why": {why}{extra}}}'


def test_a_verdict_of_either_kind_round_trips() -> None:
    """The states, problems and stamps come back as written."""
    refused = judged(["p1", "p2"], TREE, HEAD)
    unjudged = CannotJudge(["why"])
    for verdict in (_ok(), refused, unjudged):
        assert parse_verdict(verdict_text(verdict)) == verdict
    assert (_ok().state, refused.state) == (State.OK, State.PROBLEMS)


@pytest.mark.parametrize(
    "verdict",
    [
        Judged(State.CANNOT_JUDGE, NONE, TREE, HEAD),
        Judged(State.OK, ["x"], TREE, HEAD),
        Judged(State.PROBLEMS, NONE, TREE, HEAD),
        Judged(State.OK, NONE, "", HEAD),
        Judged(State.OK, NONE, TREE, "x"),
        CannotJudge(NONE),
    ],
)
def test_the_writer_refuses_a_verdict_the_reader_would_not_read_back(
    verdict: Verdict,
) -> None:
    """Unknown, contradictory, unstamped or reasonless: never written."""
    with pytest.raises(VerdictError):
        verdict_text(verdict)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        "[]",
        '"ok"',
        "{}",
        '{"state": 1}',
        UNKNOWN_STATE,
        _judged_raw(state="fine"),
        _judged_raw(problems='"none"'),
        _judged_raw(problems="[1]"),
        _judged_raw(problems='["x"]'),
        _judged_raw(state="problems"),
        _judged_raw(tree="1"),
        _judged_raw(tree='"1"'),
        _judged_raw(head="null"),
        _judged_raw(head='""'),
        _judged_raw(extra=', "note": 1'),
        f'{{"state": "ok", "problems": [], "tree": "{TREE}"}}',
        f'{{"state": "ok", "tree": "{TREE}", "head": "{HEAD}"}}',
        _cannot_raw(why="[]"),
        _cannot_raw(why='"x"'),
        _cannot_raw(why="[1]"),
        _cannot_raw(extra=f', "tree": "{TREE}"'),
        _cannot_raw(extra=', "problems": []'),
        '{"state": "cannot_judge"}',
    ],
)
def test_anything_unreadable_or_of_the_wrong_shape_cannot_judge(text: str) -> None:
    """A field missing or extra for its state, a bad stamp, bad JSON: never a pass."""
    verdict = parse_verdict(text)
    assert isinstance(verdict, CannotJudge)
    assert verdict.why


def test_a_well_formed_verdict_of_each_shape_is_read() -> None:
    """The control: the same builders, well formed, parse as what they are."""
    assert isinstance(parse_verdict(_judged_raw()), Judged)
    assert isinstance(parse_verdict(_judged_raw("problems", '["p"]')), Judged)
    assert isinstance(parse_verdict(_cannot_raw()), CannotJudge)


def test_named_inputs_holds_or_names_the_unlisted_module() -> None:
    """The judgment of nemik:W2087 as a verdict, stamped with the facts' tree and HEAD."""
    assert _run("named_inputs", TRACKED, SRC_LIST, TESTS_LIST) == _ok()
    more = TRACKED + "src/nemik/c.py\n"
    found = _run("named_inputs", more, SRC_LIST, TESTS_LIST)
    assert isinstance(found, Judged)
    assert (found.state, found.tree, found.head) == (State.PROBLEMS, TREE, HEAD)
    assert found.problems


def test_wheels_hold_or_name_the_untracked_wheel() -> None:
    """A wheel the pyproject names and the tree does not track is a problem."""
    tracked = TRACKED + WHEEL + "\n"
    assert _run("wheels", tracked, PYPROJECT) == _ok()
    found = _run("wheels", TRACKED, PYPROJECT)
    assert isinstance(found, Judged)
    assert found.state is State.PROBLEMS
    assert WHEEL in found.problems[0]


def test_the_working_card_rule_is_stamped_with_tree_and_head() -> None:
    """Code changed, cards ready, none working: problems; a working card: ok."""
    refused = _run("working_card", CHANGED, READY)
    assert refused == Judged(State.PROBLEMS, [NO_WORKING_CARD], TREE, HEAD)
    assert _run("working_card", CHANGED, WORKING) == _ok()


@pytest.mark.parametrize(
    ("kind", "texts"),
    [
        ("named_inputs", [CHANGED, SRC_LIST, TESTS_LIST]),
        ("wheels", [CHANGED, PYPROJECT]),
        ("working_card", [TRACKED, READY]),
        ("wheels", [f"facts tracked\ntree {TREE}\n{PATHS}", PYPROJECT]),
    ],
)
def test_facts_of_the_wrong_kind_or_without_a_head_cannot_judge(
    kind: str, texts: list[str]
) -> None:
    """Another facts file's text, or a tracked file with no head stamp, is refused."""
    assert isinstance(_run(kind, *texts), CannotJudge)


def test_a_missing_input_or_the_wrong_input_count_cannot_judge(tmp_path: Path) -> None:
    """The action always writes a verdict; what it could not read is a CannotJudge."""
    present = tmp_path / "tracked.txt"
    present.write_text(TRACKED, encoding="utf-8")
    gone = tmp_path / "gone.txt"
    assert isinstance(judge("wheels", [present, gone]), CannotJudge)
    assert isinstance(judge("wheels", [present]), CannotJudge)
    assert isinstance(judge("nonesuch", [present]), CannotJudge)


def test_the_status_is_read_from_the_state() -> None:
    """0 held, 1 refused, 7 not judged; a problem beats an unjudged verdict."""
    unjudged = CannotJudge(["x"])
    refused = judged(["p"], TREE, HEAD)
    assert exit_status([_ok(), _ok()], TREE, HEAD) == (0, NONE)
    assert exit_status([_ok(), refused], TREE, HEAD) == (1, ["p"])
    assert exit_status([_ok(), unjudged], TREE, HEAD) == (UNREAD, ["x"])
    both, _ = exit_status([unjudged, refused], TREE, HEAD)
    none, _ = exit_status([], TREE, HEAD)
    assert (both, none) == (1, UNREAD)


@pytest.mark.parametrize("verdict", [_ok(OTHER, HEAD), _ok(TREE, OTHER)])
def test_a_stale_verdict_is_not_judged(verdict: Judged) -> None:
    """A verdict stamped for another tree or another HEAD is never a pass."""
    status, lines = exit_status([verdict], TREE, HEAD)
    assert status == UNREAD
    assert "stale verdict" in lines[0]


@pytest.mark.parametrize(("tree", "head"), [("", HEAD), (TREE, "x"), ("xyz", "")])
def test_a_gate_that_names_no_tree_or_head_cannot_judge(tree: str, head: str) -> None:
    """The caller's own stamps must be shas, so a verdict is never compared to nothing."""
    status, _ = exit_status([_ok()], tree, head)
    assert status == UNREAD


def test_the_tool_writes_a_verdict_and_exits_zero_whatever_it_found(
    tmp_path: Path,
) -> None:
    """Build actions never fail on a judgment: the state carries it."""
    tracked = tmp_path / "tracked.txt"
    tracked.write_text(TRACKED, encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT, encoding="utf-8")
    out = tmp_path / "wheels.json"
    argv = [sys.executable, str(TOOL), "judge", "wheels", str(out)]
    ran = capture([*argv, str(tracked), str(pyproject)])
    assert ran.returncode == 0
    assert parse_verdict(out.read_text(encoding="utf-8")) == judged(
        [f"not tracked (git add -f): {WHEEL}"], TREE, HEAD
    )
    gone = capture([*argv, "nope"])
    assert gone.returncode == 0
    assert isinstance(parse_verdict(out.read_text(encoding="utf-8")), CannotJudge)


def test_the_gate_maps_the_verdict_directory_to_zero_one_or_seven(
    tmp_path: Path,
) -> None:
    """The drills: held, refused, a planted unknown state, a stale stamp, a missing file."""
    _all_ok(tmp_path)
    assert _status(tmp_path) == 0
    _write(tmp_path, "wheels", verdict_text(judged(["p"], TREE, HEAD)))
    assert _status(tmp_path) == 1
    _write(tmp_path, "wheels", UNKNOWN_STATE)
    assert _status(tmp_path) == UNREAD
    _all_ok(tmp_path)
    assert _status(tmp_path, OTHER, HEAD) == UNREAD
    assert _status(tmp_path, TREE, OTHER) == UNREAD
    (tmp_path / "wheels.json").unlink()
    assert _status(tmp_path) == UNREAD
    unjudged = [v for v in read_dir(tmp_path) if isinstance(v, CannotJudge)]
    assert len(unjudged) == 1


def test_the_gate_script_wires_the_facts_repository_and_the_state_mapping() -> None:
    """Whole code lines: every build and test call injects the repo; the state maps to exit."""
    lines = GATE.read_text(encoding="utf-8").splitlines()
    code = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    inject = (
        'build | test) "$admit" -- /usr/bin/bazel "$sub" '
        '"--inject_repository=gate_facts=$wt/.gate-facts" "$@" ;;'
    )
    verdict = "bazel test //:gate_checks_verdict --noshow_progress || verdict_rc=$?"
    status = (
        '.venv/bin/python3 tools/gate_verdict.py status "$wt/bazel-bin/gate_verdicts" '
        '"$tree" "$head_sha" || verdict_status=$?'
    )
    fast = "fast=(//:test_skill //:test_workflows //:test_architecture)"
    assert code.count(inject) == 1
    assert code.count(verdict) == 1
    assert code.count(status) == 1
    assert code.index(verdict) < code.index(status) < code.index(fast)
    assert 'exit "$verdict_status"' in code
    assert not [ln for ln in code if "NEMIK_GATE_" in ln]
