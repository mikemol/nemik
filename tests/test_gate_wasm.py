# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2379: the gate's core.wasm check names Codon by label and never skips."""

import hashlib
import os
from pathlib import Path
from typing import NamedTuple

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]
GATE_WASM = ROOT / "tools" / "gate_wasm.sh"
BUILD_WASM = ROOT / "tools" / "build_wasm.sh"
GATE = ROOT / "tools" / "gate_staged.sh"
PLANTED = "external/planted+codon/bin/codon"
WASM = "wasm"
GOOD_SHA = hashlib.sha256(WASM.encode()).hexdigest()
CANNOT_RUN = 7
USAGE = 2


class Plan(NamedTuple):
    """What the stub world says: bazel's answers, the Codon's mode, the build's status, the hash."""

    cquery: str = PLANTED
    cquery_rc: int = 0
    codon_mode: int = 0o755
    build_rc: int = 0
    sha: str = GOOD_SHA


DEFAULT = Plan()


def _script(path: Path, *lines: str) -> Path:
    path.write_text("#!/bin/sh\n" + "\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _world(tmp: Path, plan: Plan = DEFAULT) -> tuple[list[str], Path, Path]:
    """Build a stub bazel, a stub output base with a planted Codon, and a worktree.

    The stub answers `info output_base` and nothing else: asking for another info key is a failure.

    Returns:
        The bazel command words, the worktree, and the output base.

    """
    exec_root = tmp / "execroot"
    codon = exec_root / PLANTED
    codon.parent.mkdir(parents=True)
    _script(codon, "exit 0")
    codon.chmod(plan.codon_mode)
    bazel = _script(
        tmp / "bazel",
        'case "$1" in',
        f"cquery) printf '%s' '{plan.cquery}'; exit {plan.cquery_rc} ;;",
        f"info) [ \"$2\" = output_base ] || exit 9; printf '%s' '{exec_root}' ;;",
        "esac",
    )
    wt = tmp / "wt"
    (wt / "tools").mkdir(parents=True)
    (wt / "src" / "nemik" / "web").mkdir(parents=True)
    (wt / "src" / "nemik" / "web" / "core.wasm.sha256").write_text(
        f"{plan.sha}  core.wasm\n", encoding="utf-8"
    )
    rc = plan.build_rc
    _script(
        wt / "tools" / "build_wasm.sh",
        'printf "%s" "$CODON" > "$(dirname "$0")/codon.seen"',
        f'[ {rc} -eq 0 ] || echo "build_wasm: a tool is not available" >&2',
        f'[ {rc} -ne 0 ] || printf {WASM} > "$1"',
        f"exit {rc}",
    )
    return [str(bazel)], wt, exec_root


def _run(words: list[str], wt: Path) -> tuple[int, str]:
    argv = ["sh", str(GATE_WASM), "run", str(wt), str(wt), *words]
    done = capture(argv)
    return done.returncode, done.stderr


def _seen(wt: Path) -> str | None:
    path = wt / "tools" / "codon.seen"
    return path.read_text(encoding="utf-8") if path.exists() else None


def test_the_codon_given_to_the_build_is_the_one_bazel_names(tmp_path: Path) -> None:
    """A planted cquery answer reaches the build as CODON: the path is bazel's, no literal."""
    words, wt, exec_root = _world(tmp_path)
    status, err = _run(words, wt)
    assert (status, err) == (0, "")
    assert _seen(wt) == f"{exec_root}/{PLANTED}"


def test_a_cquery_that_fails_or_names_nothing_cannot_run(tmp_path: Path) -> None:
    """No path from bazel: exit 7 with the reason, and the build never starts."""
    for answer, rc in ((PLANTED, 1), ("", 0)):
        words, wt, _ = _world(tmp_path / f"w{rc}", Plan(cquery=answer, cquery_rc=rc))
        status, err = _run(words, wt)
        assert status == CANNOT_RUN
        assert "did not name @codon//:bin/codon" in err
        assert _seen(wt) is None


def test_a_codon_that_is_not_an_executable_file_cannot_run(tmp_path: Path) -> None:
    """The path bazel names must be executable, or the step cannot run."""
    words, wt, _ = _world(tmp_path, Plan(codon_mode=0o644))
    status, err = _run(words, wt)
    assert status == CANNOT_RUN
    assert "is not an executable file" in err
    assert _seen(wt) is None


def test_a_missing_tool_in_the_build_is_cannot_run_not_a_skip(tmp_path: Path) -> None:
    """build_wasm.sh's exit 7 is the gate step's exit 7 with its reason: never a pass."""
    words, wt, _ = _world(tmp_path, Plan(build_rc=CANNOT_RUN))
    status, err = _run(words, wt)
    assert status == CANNOT_RUN
    assert "a tool is not available" in err


def test_any_other_build_failure_or_a_different_hash_refuses(tmp_path: Path) -> None:
    """A failed build and a module that is not what the core builds are exit 1."""
    words, wt, _ = _world(tmp_path / "a", Plan(build_rc=5))
    assert _run(words, wt)[0] == 1
    words, wt, _ = _world(tmp_path / "b", Plan(sha="0" * 64))
    status, err = _run(words, wt)
    assert status == 1
    assert "is not what src/nemik/core builds" in err


def test_the_codon_mode_prints_the_path_or_cannot_run(tmp_path: Path) -> None:
    """The mode a hand run of build_wasm.sh uses."""
    words, _, exec_root = _world(tmp_path / "a")
    ok = capture(["sh", str(GATE_WASM), "codon", *words])
    assert (ok.returncode, ok.stdout) == (0, f"{exec_root}/{PLANTED}\n")
    words, _, _ = _world(tmp_path / "b", Plan(cquery_rc=1))
    assert capture(["sh", str(GATE_WASM), "codon", *words]).returncode == CANNOT_RUN


def test_a_call_without_a_mode_is_a_usage_error() -> None:
    """The script says how it is called."""
    assert capture(["sh", str(GATE_WASM)]).returncode == USAGE


def test_build_wasm_names_which_tool_is_absent_and_exits_seven(tmp_path: Path) -> None:
    """The pinned Codon and the host's LLVM are both CANNOT_RUN, each saying which."""
    path = os.environ["PATH"]
    gone = tmp_path / "nowhere"
    codon = _script(tmp_path / "codon", "exit 0")
    lost = capture(["sh", str(BUILD_WASM)], env={"PATH": path, "CODON": str(gone)})
    assert lost.returncode == CANNOT_RUN
    assert "the pinned Codon" in lost.stderr
    llvm = capture(
        ["sh", str(BUILD_WASM)],
        env={"PATH": path, "CODON": str(codon), "LLVM_BIN": str(gone)},
    )
    assert llvm.returncode == CANNOT_RUN
    assert "the host's LLVM tool" in llvm.stderr


def test_the_gate_script_calls_the_step_and_refuses_on_any_status() -> None:
    """One whole code line calls it; any nonzero status exits with it."""
    lines = GATE.read_text(encoding="utf-8").splitlines()
    code = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    call = (
        'sh tools/gate_wasm.sh run "$real_root" "$wt" "$admit" -- /usr/bin/bazel '
        "|| wasm_status=$?"
    )
    assert code.count(call) == 1
    assert code.index(call) < code.index('exit "$wasm_status"')
    assert not [ln for ln in code if "-eq 3" in ln and "wasm" in ln]
