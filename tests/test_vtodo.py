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


def test_nemik_tasks_feeds_the_helper_and_returns_its_exit_code(tmp_path) -> None:
    """nemik:W121: one entry point for luthen's timer: no shell pipe, the helper's 0/1/2 preserved."""
    import json
    import subprocess
    import sys

    import installed

    q = tmp_path / "root" / "life" / ".claude"
    q.mkdir(parents=True)
    (q / "paths-forward.json").write_text(json.dumps({"version": 1, "project_root": "/x", "counter": 1, "residue": [],
        "waypoints": [{"symbol": "W9", "title": "cpr", "status": "blocked", "blocked_kind": "human",
                       "blocked_on": ["operator: act attend the class"]}]}))
    opt = tmp_path / "ics.toml"
    opt.write_text('repos = ["*"]\n')
    helper = tmp_path / "helper"
    # Stand-in for nemik-akonadi-tasks: echo what it was asked, count the VTODOs on stdin, exit 1.
    helper.write_text(f"#!{sys.executable}\nimport sys\nfeed = sys.stdin.read()\n"
                      "print('ARGS', ' '.join(sys.argv[1:]), 'TODOS', feed.count('BEGIN:VTODO'))\nsys.exit(1)\n")
    helper.chmod(0o755)
    base = ["--root", str(tmp_path / "root"), "--opt-in", str(opt), "--list", "nemik"]
    r = installed.run("nemik-tasks", *base, "--helper", str(helper), "--apply")
    assert r.returncode == 1
    assert "ARGS --list nemik --apply TODOS 1" in r.stdout
    r = installed.run("nemik-tasks", *base, "--helper", str(tmp_path / "missing"))
    assert r.returncode == 2 and "setup.sh" in r.stdout
