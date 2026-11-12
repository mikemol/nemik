# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W157: mtools' mikemol-ics is installed in nemik's venv and reads an exported calendar."""


from typing import TYPE_CHECKING

import installed
from mikemol.procrun.proc import capture

if TYPE_CHECKING:
    from pathlib import Path

ICS = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:a@test\r\n"
    "DTSTAMP:20261001T000000Z\r\n"
    "DTSTART:20261003T150000Z\r\n"
    "DTEND:20261003T160000Z\r\n"
    "SUMMARY:dentist\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_mikemol_ics_reads_an_exported_calendar(tmp_path: Path) -> None:
    """Mikemol ics reads an exported calendar."""
    src = tmp_path / "cal.ics"
    src.write_text(ICS, newline="")
    ran = capture(
        [
            *installed.script("mikemol-ics"),
            "--from",
            "2026-10-01",
            "--window",
            "14d",
            "--json",
            str(src),
        ],
        env=installed.bin_env()[1],
    )
    assert ran.returncode == 0, ran.stderr
    out = ran.stdout
    assert "dentist" in out, out[:400]
    assert "a@test" in out, out[:400]
