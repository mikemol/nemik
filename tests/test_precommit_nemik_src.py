# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2087: the pre-commit refuses a src/nemik commit whose named-inputs list is stale.

The hook is run for real in a throwaway repository with a staged module and a staged list. The guard
judges the STAGED list (git show :path) against the index, run through MIKEMOL_REAL_ROOT, so a stale
staged list is refused whatever the working copy holds, and the commit gate's isolated path (a plain
snapshot as the working directory) is covered too. A fresh list passes the check and the hook then
dies at the final exec (the repository has no gate script, status 126 or 127), as in
test_precommit_queue_check. NOT EXERCISED: the real bazel (a stand-in is on PATH).
"""

import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from mikemol.procrun.proc import capture
from nemik_src import render

HERE = Path(__file__).parent
HOOK = HERE.parent / ".githooks" / "pre-commit"
TOOL = HERE.parent / "tools" / "nemik_src.py"
QUIET_QUEUE = '{"waypoints": [{"symbol": "W1", "status": "done"}]}'
MODULES = ["src/nemik/a.py", "src/nemik/b.py"]
REFUSED = 1
REFUSAL = "does not name the tracked python files"


@dataclass(frozen=True)
class Opts:
    """How one hook run differs from the plain case.

    Attributes:
        snapshot: Run with a plain directory (no repository) as the working directory.
        real_has_tool: Whether the real root holds tools/nemik_src.py (HEAD's files under
            mikemol-commit lack a tool the stack adds).
        fail_on: Put a git on PATH that exits 128 for any call carrying this argument (`diff`
            for every diff, `bazel/nemik_src.bzl` for the named-inputs listing only) and runs
            every other call for real.
        queue: The staged queue file.
        no_real_root: Leave MIKEMOL_REAL_ROOT unset, so the hook finds the checkout itself.

    """

    snapshot: bool = False
    real_has_tool: bool = True
    fail_on: str = ""
    queue: str = QUIET_QUEUE
    no_real_root: bool = False


def _git(repo: Path, *args: str) -> None:
    done = capture(["git", "-C", str(repo), *args])
    assert done.returncode == 0, done.stderr


def _run(
    tmp: Path,
    staged: list[str],
    worktree: list[str] | None = None,
    opts: Opts | None = None,
) -> tuple[int, str]:
    """Run the hook over a repo that tracks MODULES and stages a list naming `staged`.

    Args:
        tmp: A scratch directory.
        staged: The module names in the staged list.
        worktree: The names in the working copy's list when it differs from the staged one.
        opts: How this run differs from the plain case.

    Returns:
        The hook's exit status and its standard error.

    """
    opts = opts or Opts()
    repo = tmp / "repo"
    listing = repo / "bazel" / "nemik_src.bzl"
    (repo / "bazel").mkdir(parents=True)
    (repo / "tools").mkdir()
    (repo / ".claude").mkdir()
    _git(repo, "init", "-q")
    (repo / "pyproject.toml").write_text("", encoding="utf-8")
    (repo / ".claude" / "paths-forward.json").write_text(opts.queue, encoding="utf-8")
    if opts.real_has_tool:
        shutil.copy(TOOL, repo / "tools" / "nemik_src.py")
    listing.write_text(render(staged), encoding="utf-8")
    for module in MODULES:
        (repo / module).parent.mkdir(parents=True, exist_ok=True)
        (repo / module).write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    if worktree is not None:
        listing.write_text(render(worktree), encoding="utf-8")
    bindir = tmp / "bin"
    bindir.mkdir()
    fake = bindir / "bazel"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    real_git = shutil.which("git")
    if opts.fail_on:
        shim = bindir / "git"
        wanted = shlex.quote(opts.fail_on)
        shim.write_text(
            f'#!/bin/sh\nfor a in "$@"; do [ "$a" = {wanted} ] && exit 128; done\n'
            f'exec {shlex.quote(str(real_git))} "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    env.pop("NEMIK_HOOK_SNAPSHOT", None)
    env["MIKEMOL_REAL_ROOT"] = str(repo)
    if opts.no_real_root:
        env.pop("MIKEMOL_REAL_ROOT")
    env["NEMIK_PYTHON"] = sys.executable
    plain = tmp / "plain"
    (plain / "tools").mkdir(parents=True)
    shutil.copy(TOOL, plain / "tools" / "nemik_src.py")
    # Under mikemol-commit the cwd is a snapshot of the staged files, so it holds the tool even when
    # the real root (HEAD's files) does not; the hook must run the snapshot's tool.
    done = capture(["sh", str(HOOK)], cwd=plain if opts.snapshot else repo, env=env)
    return done.returncode, done.stderr


def test_the_tool_is_read_from_the_snapshot_not_the_real_root(tmp_path: Path) -> None:
    """The real gate's first misfire: the real root held HEAD's files, with no tool yet."""
    no_tool = Opts(snapshot=True, real_has_tool=False)
    stale = _run(tmp_path / "stale", MODULES[:1], opts=no_tool)
    assert stale[0] == REFUSED
    assert REFUSAL in stale[1]
    assert "can't open file" not in stale[1]
    fresh = _run(tmp_path / "fresh", MODULES, opts=no_tool)
    assert REFUSAL not in fresh[1]
    assert "can't open file" not in fresh[1]
    assert fresh[0] != REFUSED


def test_a_stale_list_is_refused(tmp_path: Path) -> None:
    """A tracked module the list does not name stops the commit."""
    status, err = _run(tmp_path, MODULES[:1])
    assert status == REFUSED
    assert REFUSAL in err


def test_a_fresh_list_passes_the_check(tmp_path: Path) -> None:
    """With the list exact, the hook goes on to the gate (dying there, as no gate script exists)."""
    status, err = _run(tmp_path, MODULES)
    assert REFUSAL not in err
    assert status != REFUSED


def test_a_stale_staged_list_is_refused_though_the_working_copy_is_fresh(
    tmp_path: Path,
) -> None:
    """The commit carries the staged list, so that is the one judged."""
    status, err = _run(tmp_path, MODULES[:1], MODULES)
    assert status == REFUSED
    assert REFUSAL in err


def test_a_fresh_staged_list_passes_though_the_working_copy_is_stale(
    tmp_path: Path,
) -> None:
    """The reverse: an unstaged stale copy does not matter."""
    status, err = _run(tmp_path, MODULES, MODULES[:1])
    assert REFUSAL not in err
    assert status != REFUSED


def test_staging_only_the_list_with_a_module_dropped_is_refused(tmp_path: Path) -> None:
    """The guard also fires when only bazel/nemik_src.bzl is staged, not any src/nemik file."""
    repo = tmp_path / "repo"
    (repo / "bazel").mkdir(parents=True)
    (repo / "tools").mkdir()
    (repo / ".claude").mkdir()
    _git(repo, "init", "-q")
    (repo / "pyproject.toml").write_text("", encoding="utf-8")
    (repo / ".claude" / "paths-forward.json").write_text(QUIET_QUEUE, encoding="utf-8")
    shutil.copy(TOOL, repo / "tools" / "nemik_src.py")
    listing = repo / "bazel" / "nemik_src.bzl"
    listing.write_text(render(MODULES), encoding="utf-8")
    for module in MODULES:
        (repo / module).parent.mkdir(parents=True, exist_ok=True)
        (repo / module).write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    identity = ["-c", "user.name=t", "-c", "user.email=t@t"]
    _git(repo, *identity, "commit", "-q", "-m", "base")
    listing.write_text(render(MODULES[:1]), encoding="utf-8")
    _git(repo, "add", "bazel/nemik_src.bzl")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "bazel"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    env.pop("NEMIK_HOOK_SNAPSHOT", None)
    env["MIKEMOL_REAL_ROOT"] = str(repo)
    env["NEMIK_PYTHON"] = sys.executable
    done = capture(["sh", str(HOOK)], cwd=repo, env=env)
    assert done.returncode == REFUSED
    assert REFUSAL in done.stderr


def test_a_failing_git_diff_refuses_the_working_card_rule_rather_than_skipping_it(
    tmp_path: Path,
) -> None:
    """If the staged code listing cannot be read the working-card rule cannot be judged: refused."""
    ready_queue = '{"waypoints": [{"symbol": "W1", "status": "ready"}]}'
    status, err = _run(tmp_path, MODULES, opts=Opts(fail_on="diff", queue=ready_queue))
    assert status == REFUSED
    assert "working-card rule cannot be judged" in err
    assert "commit refused" in err


def test_a_failing_named_inputs_listing_refuses_the_commit(tmp_path: Path) -> None:
    """With only the named-inputs listing failing, the working-card rule passes and this refuses."""
    status, err = _run(tmp_path, MODULES, opts=Opts(fail_on="bazel/nemik_src.bzl"))
    assert status == REFUSED
    assert "named-inputs list cannot be judged" in err
    assert "working-card rule" not in err


def test_a_failing_git_show_of_pyproject_refuses_the_wheel_check_rather_than_skipping_it(
    tmp_path: Path,
) -> None:
    """The untracked-wheel check reads the staged pyproject.toml; failing to read it refuses."""
    status, err = _run(tmp_path, MODULES, opts=Opts(fail_on=":pyproject.toml"))
    assert status == REFUSED
    assert "untracked-wheel check cannot be judged" in err
    assert "commit refused" in err


def test_a_failing_git_show_of_the_queue_refuses_with_the_cause_named(
    tmp_path: Path,
) -> None:
    """Reading the staged queue is fail-closed with a message, not only through set -e."""
    status, err = _run(
        tmp_path, MODULES, opts=Opts(fail_on=":.claude/paths-forward.json")
    )
    assert status == REFUSED
    assert "the queue cannot be read" in err
    assert "untracked-wheel" not in err


def test_a_failing_rev_parse_refuses_when_the_checkout_cannot_be_found(
    tmp_path: Path,
) -> None:
    """With no MIKEMOL_REAL_ROOT the hook asks git for the top level; a failure names the cause."""
    status, err = _run(
        tmp_path, MODULES, opts=Opts(fail_on="rev-parse", no_real_root=True)
    )
    assert status == REFUSED
    assert "the checkout cannot be found" in err


def test_the_isolated_gate_path_runs_from_a_plain_snapshot(tmp_path: Path) -> None:
    """With MIKEMOL_REAL_ROOT set and a plain directory as cwd, both verdicts still hold."""
    status, err = _run(tmp_path / "stale", MODULES[:1], opts=Opts(snapshot=True))
    assert status == REFUSED
    assert REFUSAL in err
    status, err = _run(tmp_path / "fresh", MODULES, opts=Opts(snapshot=True))
    assert REFUSAL not in err
    assert status != REFUSED
