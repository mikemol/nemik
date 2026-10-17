# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W641: nemik-check --digest prints the same findings with shared Info rows counted."""

from pathlib import Path

import pytest

from nemik.check import main

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _run(capsys: pytest.CaptureFixture[str], *flags: str) -> list[str]:
    """Run nemik-check on the fixture fleet.

    Args:
        capsys: The output capture.
        *flags: Extra flags.

    Returns:
        The lines it printed.

    """
    with pytest.raises(SystemExit):
        main(["--root", str(FLEET), *flags])
    return capsys.readouterr().out.splitlines()


def test_digest_keeps_every_non_info_row_and_never_adds_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Warnings and Violations print in full; the digest is never longer than the full list."""
    full = _run(capsys)
    digest = _run(capsys, "--digest")
    assert len(digest) <= len(full)
    keep = ("Warning", "Violation")
    assert [x for x in full if x.strip().startswith(keep)] == [
        x for x in digest if x.strip().startswith(keep)
    ]
