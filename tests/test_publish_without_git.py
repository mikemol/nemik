# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W572: a publish needs no git binary, because the pod's final image has none.

The image's final stage never carries git (only its test stage does), and the snapshot builder runs
`nemik-serve --publish` there. History is the one reader that shells out to git; with no binary it
must mean "no history", as a directory that is not a repository already does, and the build goes on.
"""

from pathlib import Path

import pytest

from nemik.history import resolve
from nemik.serve import publish

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_a_revision_lookup_without_a_git_binary_finds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With nothing on PATH a date resolves to no revision, and no error is raised."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert resolve(FLEET, "2026-01-01") is None


def test_a_publish_succeeds_without_a_git_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pod's condition: the whole snapshot builds with no git on PATH."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert publish(FLEET, tmp_path / "pub", None) is not None
