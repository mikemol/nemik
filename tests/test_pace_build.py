# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1197: the pace file's header names the build that computed it, or says unknown."""

import pytest

from nemik.hostroot_cli import UNKNOWN_BUILD, build_sha, with_build
from nemik.pacepublish import read_pace

SHA = "15d9bd68897eb12d9374094477987103118461d1"
HEADER = '{"as_of": "2026-10-28T01:34:23Z", "window": "10"}'
ROW = (
    '{"repo": "nemik", "ratchet": "mypy-baseline.json", "state": "ok", '
    '"observed": "5", "required": "2", "value": "4444", "horizon": "40"}'
)
GIT_INSTALL = f'{{"vcs_info": {{"vcs": "git", "commit_id": "{SHA}"}}}}'
# direct_url.json texts that record no whole lower-case commit: each reads as unknown
UNRECORDED = [
    "",
    "not json",
    '{"dir_info": {"editable": true}}',
    f'{{"vcs_info": {{"commit_id": "{SHA[:12]}"}}}}',
    f'{{"vcs_info": {{"commit_id": "{SHA.upper()}"}}}}',
    '{"vcs_info": {"commit_id": "dirty"}}',
    '["vcs_info"]',
]


class _Dist:
    """A stand-in installed distribution that holds one direct_url.json text."""

    def __init__(self, text: str) -> None:
        self.text = text

    def read_text(self, name: str) -> str:
        assert name == "direct_url.json"
        return self.text


def _installed(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    def distribution(_name: str) -> _Dist:
        return _Dist(text)

    monkeypatch.setattr("nemik.hostroot_cli.distribution", distribution)


def test_the_header_gains_a_third_key_and_the_file_still_reads() -> None:
    """The build is third after as_of and window, the rows are untouched, read_pace parses it."""
    text = with_build(f"{HEADER}\n{ROW}\n", SHA)
    lines = text.splitlines()
    assert lines[0] == (
        '{"as_of": "2026-10-28T01:34:23Z", "window": "10", "build": "' + SHA + '"}'
    )
    assert lines[1] == ROW
    as_of, window, rows = read_pace(text)
    assert (as_of, window, len(rows)) == ("2026-10-28T01:34:23Z", 10, 1)


def test_a_git_install_names_its_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The vcs_info commit_id of 40 lower-case hex is the build."""
    _installed(monkeypatch, GIT_INSTALL)
    assert build_sha() == SHA


def test_anything_but_a_whole_lowercase_sha_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Luthen's egress gate removes the file for a short, upper-case or free-text build."""
    for text in UNRECORDED:
        _installed(monkeypatch, text)
        assert build_sha() == UNKNOWN_BUILD, text
