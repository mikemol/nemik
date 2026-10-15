"""nemik:W521: the commit gate is one bazel target, and the hook refuses when it cannot run.

The operator's rule (2026-10-06): a pre-commit should be a bazel build with the gate logic in a BUILD file, so
BuildBuddy captures its logs. nemik's gate ran `bazel test //...` from a script; it is now `//:precommit`, a
test_suite over every test (the lint, type, shell and warrant stages join it as they land). And mtools'
principle holds: a gate refuses when it cannot run, never skips, so a missing bazel is a refused commit that
says why.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-commit"
SCRIPT = ROOT / "tools" / "gate_staged.sh"
TESTS_GLOB = 'glob(["tests/test_*.py"])'


def _code(path: Path) -> list[str]:
    """The non-comment lines of a shell file."""
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_the_gate_is_the_precommit_suite() -> None:
    assert "bazel test //:precommit" in "\n".join(_code(SCRIPT))
    assert not [line for line in _code(SCRIPT) if "bazel test //..." in line], (
        "the gate went back to //..., which is no named target"
    )


def test_the_suite_covers_every_test_target() -> None:
    build = (ROOT / "BUILD.bazel").read_text()
    suite = build[build.index("test_suite(") :]
    suite = suite[: suite.index(")\n")]
    assert 'name = "precommit"' in suite
    # the suite and the macro that makes the tests take their modules from the same glob
    assert TESTS_GLOB in suite and f"for src in {TESTS_GLOB}" in build


def test_the_hook_refuses_when_bazel_is_absent(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    run = subprocess.run(
        ["/bin/sh", str(HOOK)],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": str(empty)},
        cwd=tmp_path,
    )
    assert run.returncode == 1
    assert "bazel is not on PATH" in run.stderr
    assert "commit refused" in run.stderr


def test_the_hook_names_bazel_in_code_not_only_comments() -> None:
    assert any("bazel" in line for line in _code(HOOK))
