# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2057: the pre-commit refuses code while the queue has ready cards and no working one.

The hook is run for real in a throwaway repository with a staged queue and a staged source file.
Two hooks run over the same cases: the one at HEAD and the copy kept in tests/fixtures/precommit
(git blob 9a98a465, the version before W2053), which tests the queue text with a pipe into grep.
NOT EXERCISED: the real `bazel` (a stand-in is on PATH) and the gate script (the repository has
none, so a pass dies at the final exec, status 126 or 127, and a refusal is status 1 plus message).
"""

import hashlib
import os
from pathlib import Path

import pytest
from mikemol.procrun.proc import capture

HERE = Path(__file__).parent
NEW_HOOK = HERE.parent / ".githooks" / "pre-commit"
OLD_HOOK = HERE / "fixtures" / "precommit" / "pre-commit-before-w2053"
OLD_HOOK_BLOB = "9a98a465a6121ea1fe04d221bae23339be5e3888"
REFUSAL = "none is marked working"
READY = '{"waypoints": [{"symbol": "W1", "status": "ready"}]}'
WORKING = '{"waypoints": [{"symbol": "W1", "status": "ready"}, {"status": "working"}]}'
NEITHER = '{"waypoints": [{"symbol": "W1", "status": "done"}]}'
SPLIT = '{"waypoints": [{"symbol": "W1", "status":\n"ready"}]}'
PADDING = "\n".join(f'  "pad{n}": "{"x" * 40}",' for n in range(20_000))
BIG = (
    '{\n  "status": "ready",\n  "status2": "working", "status": "working",\n'
    + PADDING
    + "\n}"
)
PIPE_BUFFER = 65536
MIN_BIG_QUEUE = 4 * PIPE_BUFFER
REFUSED = 1
IGNORE_SIGPIPE = ["sh", "-c", 'trap "" PIPE; exec "$0" "$@"']


def _git(repo: Path, *args: str) -> None:
    done = capture(["git", "-C", str(repo), *args])
    assert done.returncode == 0, done.stderr


def _verdict(status: int, stderr: str) -> str:
    return "refuse" if status == REFUSED and REFUSAL in stderr else "pass"


def _run_hook(
    tmp: Path, script: str, case: tuple[str, str], wrapper: list[str]
) -> tuple[int, str]:
    """Run a pre-commit script text in a fresh repository and give its status and stderr.

    Returns:
        The hook's exit status and its standard error.

    """
    queue, staged = case
    repo = tmp / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "pyproject.toml").write_text("", encoding="utf-8")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "paths-forward.json").write_text(queue, encoding="utf-8")
    if staged:
        target = repo / staged
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    bindir = tmp / "bin"
    bindir.mkdir()
    fake = bindir / "bazel"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    hook = tmp / "pre-commit"
    hook.write_text(script, encoding="utf-8")
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    env.pop("NEMIK_HOOK_SNAPSHOT", None)
    env["MIKEMOL_REAL_ROOT"] = str(repo)
    done = capture([*wrapper, "sh", str(hook)], cwd=repo, env=env)
    return done.returncode, done.stderr


CASES = [
    ("ready only, code staged", (READY, "src/a.py"), "refuse"),
    ("ready and working, code staged", (WORKING, "src/a.py"), "pass"),
    ("nothing ready, code staged", (NEITHER, "src/a.py"), "pass"),
    ("ready text split over two lines, code staged", (SPLIT, "src/a.py"), "pass"),
    ("ready only, tests staged", (READY, "tests/test_a.py"), "refuse"),
    ("ready only, only the queue staged", (READY, ""), "pass"),
]
HOOKS = {"old": OLD_HOOK, "new": NEW_HOOK}


def test_the_old_hook_fixture_is_the_hook_before_w2053() -> None:
    """The fixture is the git blob of the hook at eb3fd9c8, not whatever HEAD holds later."""
    data = OLD_HOOK.read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False)
    assert blob.hexdigest() == OLD_HOOK_BLOB


@pytest.mark.parametrize("which", list(HOOKS))
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_each_hook_refuses_only_code_with_ready_cards_and_no_working_card(
    tmp_path: Path, which: str, case: tuple[str, tuple[str, str], str]
) -> None:
    """The old and the new hook give the verdict the hook's comment promises on each case."""
    name, queue_and_staged, verdict = case
    script = HOOKS[which].read_text(encoding="utf-8")
    status, stderr = _run_hook(tmp_path, script, queue_and_staged, [])
    assert _verdict(status, stderr) == verdict, (which, name, status, stderr)


def test_the_old_form_is_noisy_under_an_ignored_sigpipe_and_the_new_one_is_not(
    tmp_path: Path,
) -> None:
    """The production case is an ignored SIGPIPE and a large multi-line queue.

    The real queue is 5.8 MB. grep -q exits at the first match while printf still has more than a
    pipe buffer left to write, so the old pipe form prints Broken pipe. A one-line queue does not:
    grep reads the whole line first.
    """
    assert len(BIG) > MIN_BIG_QUEUE
    noise = {}
    for which, path in HOOKS.items():
        script = path.read_text(encoding="utf-8")
        case = (BIG, "src/a.py")
        status, stderr = _run_hook(tmp_path / which, script, case, IGNORE_SIGPIPE)
        assert _verdict(status, stderr) == "pass", (which, status, stderr)
        noise[which] = "Broken pipe" in stderr
    assert noise == {"old": True, "new": False}


def test_swapping_the_two_flags_is_caught(tmp_path: Path) -> None:
    """A hook that tests working where it tests ready gives a different verdict on some case."""
    text = NEW_HOOK.read_text(encoding="utf-8")
    mutant = text.replace(
        '[ "$has_ready" -eq 1 ] && [ "$has_working" -eq 0 ]',
        '[ "$has_ready" -eq 0 ] && [ "$has_working" -eq 1 ]',
    )
    assert mutant != text
    differing = []
    for index, (name, queue_and_staged, verdict) in enumerate(CASES):
        status, stderr = _run_hook(tmp_path / str(index), mutant, queue_and_staged, [])
        if _verdict(status, stderr) != verdict:
            differing.append(name)
    assert differing
