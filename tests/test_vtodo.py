"""nemik:W128: operator asks as RFC 5545 VTODOs, opt-in per repo."""

from nemik.vtodo import calendar, stated_ask, vtodos

ASKS = [
    {"ref": "life:W21", "title": "Resume, approve", "category": "needs-you",
     "ask": "life-0e | operator: decide approve notes/life-ems-resume.md as-is, or say what to change",
     "waiting": ["life:W10", "resumes:W1"], "same_ask": ["resumes:W2"], "last_activity": "2026-09-28T13:02:06Z"},
    {"ref": "life:W3", "title": "cadence", "category": "unstated", "ask": "operator", "waiting": [], "same_ask": []},
    {"ref": "aeternum:W48", "title": "x", "category": "needs-you", "ask": "operator: act push it",
     "waiting": [], "same_ask": []},
]


def test_only_needs_you_asks_from_opted_in_repos() -> None:
    uids = [line for t in vtodos(ASKS, {"life"}) for line in t if line.startswith("UID:")]
    assert uids == ["UID:nemik:life:W21"]
    assert vtodos(ASKS, set()) == []  # no opt-in file, nothing projected


def test_summary_is_the_stated_ask_and_relations_name_what_it_releases() -> None:
    assert stated_ask(ASKS[0]["ask"])[0] == "decide"
    (todo,) = vtodos(ASKS, {"life"}, link="http://nemik:8750")
    assert "SUMMARY:decide: approve notes/life-ems-resume.md as-is\\, or say what to change" in todo
    assert "RELATED-TO;RELTYPE=CHILD:nemik:resumes:W1" in todo
    assert "DTSTAMP:20260928T130206Z" in todo
    assert "URL:http://nemik:8750/#life:W21" in todo


def test_calendar_is_crlf_folded_and_deterministic() -> None:
    text = calendar(vtodos(ASKS, {"life", "aeternum"}))
    assert text == calendar(vtodos(ASKS, {"life", "aeternum"}))
    assert text.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n") and text.endswith("END:VCALENDAR\r\n")
    for line in text.split("\r\n"):
        assert len(line.encode()) <= 75
    assert text.count("BEGIN:VTODO") == 2


def test_star_opts_every_repo_in(tmp_path) -> None:
    from nemik.vtodo import opted_in

    f = tmp_path / "ics.toml"
    f.write_text('repos = ["*"]\n')
    assert len(vtodos(ASKS, opted_in(f))) == 2  # both needs-you asks, any repo
    assert opted_in(tmp_path / "missing.toml") == set()
