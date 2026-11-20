# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2345: the gate's git-fed judgments, read as ONE bazel test over their verdict files.

Gate only. The three judgments are build actions (//:gate_verdict_*) over facts the gate injects as
a repository, and each writes a JSON verdict. This test fails on any verdict but ok and prints the
problems, so BuildBuddy shows a failing test with its log instead of a green build the gate later
refuses. It does not replace the gate's exit mapping (bazel collapses a failing test to one code and
the gate needs 1 against 7): tools/gate_verdict.py `status` reads the same files through the same
parser. It is named gate_*.py, not test_*.py, so the image's plain pytest never collects it, and it
never skips: a verdict that is missing or cannot be read is a failure, not a pass.
"""

from pathlib import Path

import pytest
from gate_verdict import KINDS, CannotJudge, State, read_dir

# Not resolved: a sandbox's runfiles are symlinks, and resolving one would leave the sandbox.
ROOT = Path(__file__).absolute().parents[1]


def test_every_git_fed_judgment_of_the_staged_tree_holds() -> None:
    """A judgment that found problems, or could not judge, fails with what it said."""
    said: list[str] = []
    for kind, verdict in zip(KINDS, read_dir(ROOT / "gate_verdicts"), strict=True):
        if isinstance(verdict, CannotJudge):
            said.extend(f"{kind}: could not judge: {why}" for why in verdict.why)
        elif verdict.state is not State.OK:
            said.extend(f"{kind}: {problem}" for problem in verdict.problems)
    if said:
        pytest.fail("\n".join(said), pytrace=False)
