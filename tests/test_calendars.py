"""nemik:W157: calendars exported by the helper, read through mikemol-ics, temp files removed."""

import stat
from pathlib import Path

import pytest

import installed
from nemik.calendars import occurrences

ICS = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//t//EN",
                   "BEGIN:VEVENT", "UID:a@t", "DTSTAMP:20261001T000000Z", "DTSTART:20261003T150000Z",
                   "DTEND:20261003T160000Z", "SUMMARY:dentist", "END:VEVENT", "END:VCALENDAR", ""])


def _helper(tmp_path, fail=False) -> Path:
    """A stand-in for nemik-akonadi-tasks --export-calendar NAME --out FILE."""
    src = tmp_path / "src.ics"
    src.write_text(ICS, newline="")
    h = tmp_path / "helper"
    h.write_text(f"#!/bin/sh\n{'exit 2' if fail else ''}\ncp {src} \"$4\"\necho \"$4\" >> {tmp_path}/seen\n")
    h.chmod(h.stat().st_mode | stat.S_IXUSR)
    return h


@pytest.fixture
def ics(monkeypatch) -> str:
    """The venv's mikemol-ics, with the environment it needs under bazel (PYTHONHOME)."""
    for k, v in installed._bin()[1].items():
        monkeypatch.setenv(k, v)
    return installed.script("mikemol-ics")[0]


def test_occurrences_are_read_and_the_export_is_deleted(tmp_path, ics) -> None:
    got = occurrences({"home": "Personal"}, start="2026-10-01", helper=_helper(tmp_path), ics=ics)
    assert [(r["label"], r["uid"], r["summary"]) for r in got] == [("home", "a@t", "dentist")]
    exported = Path((tmp_path / "seen").read_text().strip())
    assert not exported.exists() and not exported.parent.exists()  # no copy of the calendar is left


def test_a_failed_export_raises_rather_than_reading_as_a_free_day(tmp_path, ics) -> None:
    import subprocess
    with pytest.raises(subprocess.CalledProcessError):
        occurrences({"home": "Personal"}, start="2026-10-01", helper=_helper(tmp_path, fail=True), ics=ics)


def test_config_opts_calendars_in(tmp_path) -> None:
    from nemik.calendars import load_collections

    assert load_collections(tmp_path / "missing.toml") == {}
    p = tmp_path / "calendars.toml"
    p.write_text('[calendars]\nhome = "Personal"\nwork = "Shift schedule"\n')
    assert load_collections(p) == {"home": "Personal", "work": "Shift schedule"}
    p.write_text('[calendars]\n"Home Cal" = "Personal"\n')
    with pytest.raises(ValueError, match="bad entry"):
        load_collections(p)
