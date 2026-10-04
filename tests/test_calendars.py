"""nemik:W157: calendars exported by the helper, read through mikemol-ics, temp files removed."""

import stat
from pathlib import Path

import pytest

import installed
from nemik.calendars import occurrences

ICS = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//t//EN",
                   "BEGIN:VEVENT", "UID:a@t", "DTSTAMP:20261001T000000Z", "DTSTART:20261003T150000Z",
                   "DTEND:20261003T160000Z", "SUMMARY:dentist", "END:VEVENT", "END:VCALENDAR", ""])


def _helper(tmp_path, fail=False, text: str = ICS) -> Path:
    """A stand-in for nemik-akonadi-tasks --export-calendar NAME --out FILE."""
    src = tmp_path / "src.ics"
    src.write_text(text, newline="")
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


def test_events_become_nodes_and_cal_refs_wait_on_the_next_occurrence() -> None:
    from rdflib import Graph, Literal

    from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
    from nemik.calendars import event_graph

    occs = [{"label": "home", "uid": "a@t", "start": "2026-10-03T15:00:00+00:00", "end": None, "all_day": False,
             "summary": "dentist", "recurrence_id": "2026-10-03T15:00:00+00:00"},
            {"label": "home", "uid": "a@t", "start": "2026-10-10T15:00:00+00:00", "end": None, "all_day": False,
             "summary": "dentist", "recurrence_id": "2026-10-10T15:00:00+00:00"}]
    q = Graph()
    w = waypoint_uri("life", "W9")
    q.add((w, OSLC_CM.state, STATE["blocked"]))
    q.add((w, NEMIK.blockedOn, Literal("cal:home/a@t")))
    g = event_graph(occs, q)
    assert len(set(g.subjects(None, NEMIK.Event))) == 2
    assert [str(t) for t in g.objects(w, NEMIK.waitsFor)] == ["urn:nemik:cal:home/a@t/2026-10-03T15:00:00+00:00"]


def test_operator_lists_the_next_days_with_waiters(tmp_path, ics, capsys, monkeypatch) -> None:
    """nemik:W160/W161: nemik-days N, from opted-in calendars only."""
    import datetime

    from rdflib import Graph, Literal

    from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
    from nemik.calendars import days_main

    class Today(datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 1)
    monkeypatch.setattr(datetime, "date", Today)
    monkeypatch.setenv("PATH", str(installed._bin()[0]) + ":" + __import__("os").environ["PATH"])
    g = Graph()
    w = waypoint_uri("life", "W9")
    g.add((w, OSLC_CM.state, STATE["blocked"]))
    g.add((w, NEMIK.blockedOn, Literal("cal:home/a@t")))
    cfg = tmp_path / "calendars.toml"
    days_main(["14", "--calendars", str(cfg), "--helper", str(_helper(tmp_path))], g)
    assert "no calendar opted in" in capsys.readouterr().out
    cfg.write_text('[calendars]\nhome = "Personal"\n')
    days_main(["14", "--calendars", str(cfg), "--helper", str(_helper(tmp_path))], g)
    out = capsys.readouterr().out
    assert "dentist" in out and "<- life:W9" in out


def test_the_reader_is_found_in_nemiks_own_venv_not_on_path(tmp_path, monkeypatch) -> None:
    """life-82, 2026-10-02: .venv/bin/nemik-days run without the venv on PATH could not find
    mikemol-ics. The default is the venv's own copy; a missing reader is a stated refusal."""
    from nemik.calendars import _venv_ics

    for k, v in installed._bin()[1].items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")  # the venv is not on PATH
    got = occurrences({"home": "Personal"}, start="2026-10-01", helper=_helper(tmp_path))
    assert [r["uid"] for r in got] == ["a@t"] and _venv_ics().endswith("/mikemol-ics")
    with pytest.raises(FileNotFoundError, match="calendar reader"):
        occurrences({"home": "Personal"}, start="2026-10-01", helper=_helper(tmp_path), ics=str(tmp_path / "nope"))


def test_a_refusing_helper_is_reported_not_a_traceback(tmp_path, ics, capsys) -> None:
    """nemik:W193: the Akonadi helper refuses when Akonadi is not running; nemik-days says so, exit 2."""
    from nemik.calendars import days_main

    h = tmp_path / "helper"
    h.write_text("#!/bin/sh\necho 'ERROR: akonadi is not running on this session bus; refusing to start it from here'\nexit 2\n")
    h.chmod(0o755)
    cfg = tmp_path / "calendars.toml"
    cfg.write_text('[calendars]\nhome = "Personal"\n')
    with pytest.raises(SystemExit) as e:
        days_main(["3", "--calendars", str(cfg), "--helper", str(h)], __import__("rdflib").Graph())
    assert e.value.code == 2
    out = capsys.readouterr().out
    assert "refusing to start it" in out and "Traceback" not in out


CHORES = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//t//EN"] + [
    line for i, summary in enumerate(["Trash: Mike", "Dishes: Pascal", "Supper: Pascal", "Lunch: Sam"])
    for line in ("BEGIN:VEVENT", f"UID:c{i}@t", "DTSTAMP:20261001T000000Z", f"DTSTART:2026100{3 + i}T150000Z",
                 f"DTEND:2026100{3 + i}T160000Z", f"SUMMARY:{summary}", "END:VEVENT")] + ["END:VCALENDAR", ""])


def test_calendar_entries_take_a_name_or_a_table_and_a_typo_fails(tmp_path) -> None:
    """nemik:W190 (life:W31): `label = "Name"` still works; `{ name, include }` adds the filter; an
    unknown key (a typo'd `includes` would silently mean "no filter") and a bad include fail."""
    from nemik.calendars import Calendar, load_calendars, load_collections

    p = tmp_path / "calendars.toml"
    p.write_text('[calendars]\nhome = "Personal"\nchores = { name = "Chores", include = ["Mike", "Supper: Pascal"] }\n')
    assert load_calendars(p) == {"chores": Calendar("Chores", ("Mike", "Supper: Pascal")), "home": Calendar("Personal")}
    assert load_collections(p) == {"chores": "Chores", "home": "Personal"}
    for bad in ('chores = { name = "Chores", includes = ["Mike"] }', 'chores = { name = "Chores", include = "Mike" }',
                'chores = { name = "Chores", include = [""] }', 'chores = { include = ["Mike"] }'):
        p.write_text(f"[calendars]\n{bad}\n")
        with pytest.raises(ValueError, match="bad entry"):
            load_calendars(p)


def test_include_keeps_case_sensitive_substring_matches_and_counts_both_ways(tmp_path, ics) -> None:
    got_all: dict = {}
    occurrences({"chores": "Chores"}, start="2026-10-01", helper=_helper(tmp_path, text=CHORES), ics=ics, stats=got_all)
    assert got_all == {"chores": (4, 4)}  # no include: everything
    stats: dict = {}
    got = occurrences({"chores": "Chores"}, start="2026-10-01", helper=_helper(tmp_path, text=CHORES), ics=ics,
                      includes={"chores": ("Mike", "Supper: Pascal")}, stats=stats)
    assert [r["summary"] for r in got] == ["Trash: Mike", "Supper: Pascal"] and stats == {"chores": (2, 4)}
    none: dict = {}
    assert not occurrences({"chores": "Chores"}, start="2026-10-01", helper=_helper(tmp_path, text=CHORES), ics=ics,
                           includes={"chores": ("mike",)}, stats=none)  # case-sensitive: "mike" is not "Mike"
    assert none == {"chores": (0, 4)}


def test_a_filter_that_matches_nothing_is_reported_not_read_as_a_free_day(tmp_path, ics, capsys, monkeypatch) -> None:
    import datetime

    from nemik.calendars import days_main

    class Today(datetime.date):  # the window starts today: pin it so the fixture dates stay inside it
        @classmethod
        def today(cls):
            return cls(2026, 10, 1)
    monkeypatch.setattr(datetime, "date", Today)

    cfg = tmp_path / "calendars.toml"
    cfg.write_text('[calendars]\nchores = { name = "Chores", include = ["Nobody"] }\n')
    days_main(["14", "--calendars", str(cfg), "--helper", str(_helper(tmp_path, text=CHORES))], __import__("rdflib").Graph())
    out = capsys.readouterr().out
    assert "next 14 days (0)" in out and "filter chores: 0 of 4 matched" in out and "not a free day" in out


def _row(label, start, summary, waiting=()):
    return {"label": label, "uid": "u", "start": start, "end": None, "all_day": False, "summary": summary,
            "recurrence_id": start, "waiting": list(waiting)}


def test_dedupe_merges_across_calendars_never_within_one() -> None:
    """nemik:W191: the same entry in two calendars is one row naming the other; two identical entries
    inside one calendar are two real events; waiters from both copies are kept."""
    from nemik.calendars import dedupe

    rows = [_row("household", "2026-10-05T09:00", "Trash: Mike", ["life:W9"]),
            _row("main", "2026-10-05T09:00", "Trash: Mike", ["life:W10"]),
            _row("main", "2026-10-05T09:00", "Trash: Mike"),  # a third copy, in a calendar already represented
            _row("main", "2026-10-05T09:00", "Dishes: Pascal"),
            _row("main", "2026-10-06T09:00", "Dishes: Pascal"),
            _row("chores", "2026-10-06T09:00", "Dishes: Pascal"),
            _row("chores", "2026-10-06T09:00", "Dishes: Pascal")]  # two real events in ONE calendar
    got = dedupe(rows)
    assert [(r["label"], r["summary"], r.get("also")) for r in got] == [
        ("household", "Trash: Mike", ["main"]), ("main", "Trash: Mike", None), ("main", "Dishes: Pascal", None),
        ("main", "Dishes: Pascal", ["chores"]), ("chores", "Dishes: Pascal", None)]
    assert got[0]["waiting"] == ["life:W10", "life:W9"]  # both copies' waiters
    assert "also" not in rows[0]  # the input is not mutated


def test_days_dedupes_across_calendars_and_no_dedupe_shows_all(tmp_path, ics, capsys, monkeypatch) -> None:
    import datetime

    from nemik.calendars import days_main

    class Today(datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 1)
    monkeypatch.setattr(datetime, "date", Today)
    cfg = tmp_path / "calendars.toml"
    cfg.write_text('[calendars]\nhousehold = "A"\nmain = "B"\n')  # the stand-in exports the same ICS for both
    base = ["14", "--calendars", str(cfg), "--helper", str(_helper(tmp_path, text=CHORES))]
    g = __import__("rdflib").Graph()
    days_main(base, g)
    out = capsys.readouterr().out
    assert "next 14 days (4)" in out and "[also: main]" in out
    days_main([*base, "--no-dedupe"], g)
    assert "next 14 days (8)" in capsys.readouterr().out
