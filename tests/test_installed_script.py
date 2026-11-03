# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1566: installed.script names an uninstalled script with FileNotFoundError."""

from pathlib import Path

import installed
import pytest


def test_an_uninstalled_script_is_a_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uninstalled script raises FileNotFoundError naming the script and its directory.

    It used to be an assert: AssertionError, and gone under python -O (nemik:W1565).
    """

    def empty_bin() -> tuple[Path, dict[str, str]]:
        return tmp_path, {}

    monkeypatch.setattr(installed, "_bin", empty_bin)
    with pytest.raises(FileNotFoundError, match="nemik-absent is not installed in"):
        installed.script("nemik-absent")
