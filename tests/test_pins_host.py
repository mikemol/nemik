# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W379: nemik-pins reads the host's uv install receipt for nemik and names its commit."""

from __future__ import annotations

from pathlib import Path

from nemik.pins import installed

SHA = "697942ebd41dd2dbb17d77facef34c84f581f9ee"


def test_the_receipt_names_the_installed_commit(tmp_path: Path) -> None:
    receipt = tmp_path / "uv-receipt.toml"
    receipt.write_text(
        "[tool]\n"
        f'requirements = [{{ name = "nemik", git = "file:///x/nemik?rev={SHA}" }}]\n'
    )
    assert installed(receipt) == SHA


def test_no_receipt_or_another_tool_is_not_an_install(tmp_path: Path) -> None:
    assert installed(tmp_path / "absent.toml") is None
    other = tmp_path / "uv-receipt.toml"
    other.write_text('[tool]\nrequirements = [{ name = "ruff" }]\n')
    assert installed(other) is None
