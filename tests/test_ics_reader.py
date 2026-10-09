"""nemik:W157: mtools' mikemol-ics is installed in nemik's venv and reads an exported calendar."""

import subprocess

import installed

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


def test_mikemol_ics_reads_an_exported_calendar(tmp_path) -> None:
    src = tmp_path / "cal.ics"
    src.write_text(ICS, newline="")
    out = subprocess.run(
        [
            *installed.script("mikemol-ics"),
            "--from",
            "2026-10-01",
            "--window",
            "14d",
            "--json",
            str(src),
        ],
        capture_output=True,
        text=True,
        env=installed._bin()[1],
        check=True,
    ).stdout
    assert "dentist" in out and "a@test" in out, out[:400]
