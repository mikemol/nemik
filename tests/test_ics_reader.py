"""nemik:W157: mtools' mikemol-ics is installed in nemik's venv and reads an exported calendar."""

import subprocess

import installed

ICS = "\r\n".join([
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//EN",
    "BEGIN:VEVENT", "UID:a@test", "DTSTAMP:20261001T000000Z", "DTSTART:20261003T150000Z",
    "DTEND:20261003T160000Z", "SUMMARY:dentist", "END:VEVENT",
    "END:VCALENDAR", ""])


def test_mikemol_ics_reads_an_exported_calendar(tmp_path) -> None:
    src = tmp_path / "cal.ics"
    src.write_text(ICS, newline="")
    out = subprocess.run([*installed.script("mikemol-ics"), "--from", "2026-10-01", "--window", "14d", "--json", str(src)],
                         capture_output=True, text=True, env=installed._bin()[1], check=True).stdout
    assert "dentist" in out and "a@test" in out, out[:400]
