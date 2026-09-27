import os
import shutil

import pytest

from nemik.witnesses import witness

pytestmark = pytest.mark.skipif(shutil.which("opa") is None, reason="opa not installed")


def test_file_witness_true_false(tmp_path) -> None:
    p = tmp_path / "flag"
    q = f'input.file["{p}"].exists'
    assert witness(q)[0] == "false"
    p.write_text("")
    verdict, doc, _ = witness(q)
    assert verdict == "true"
    assert doc["file"][str(p)] == {"exists": True}


def test_pid_witness_sees_live_and_gone() -> None:
    live = f'not input.pid["localhost/{os.getpid()}"].alive'
    assert witness(live)[0] == "false"
    assert witness('not input.pid["localhost/999999999"].alive')[0] == "true"


def test_pid_reuse_guard_treats_other_starttime_as_gone() -> None:
    assert witness(f'not input.pid["localhost/{os.getpid()}@1"].alive')[0] == "true"


def test_unobservable_fact_is_undefined_not_false() -> None:
    verdict, _, missing = witness('not input.pid["otherhost/1"].alive')
    assert verdict == "undefined" and missing == ['pid["otherhost/1"]']
    assert witness('input.nosuch["x"].ok')[0] == "undefined"


def test_time_witness_uses_input_now() -> None:
    from datetime import UTC, datetime

    q = 'time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("2026-10-01T00:00:00Z")'
    assert witness(q, now=datetime(2026, 9, 30, tzinfo=UTC))[0] == "false"
    assert witness(q, now=datetime(2026, 10, 2, tzinfo=UTC))[0] == "true"


def test_git_ref_witness(tmp_path, monkeypatch) -> None:
    import subprocess

    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    monkeypatch.setenv("NEMIK_ROOT", str(tmp_path))
    assert witness('input.git_ref["r@main"].exists')[0] == "true"
    assert witness('input.git_ref["r@nope"].exists')[0] == "false"
    assert witness('input.git_ref["absent@main"].exists')[0] == "undefined"
    assert witness('input.git_ref["r@--output=x"].exists')[0] == "undefined"
    assert witness('input.git_ref["../r@main"].exists')[0] == "undefined"


def test_runner_applies_only_holding_witnesses(tmp_path, monkeypatch, capsys) -> None:
    import json
    import sys

    from nemik import witnesses

    flag = tmp_path / "flag"
    flag.write_text("")
    q = tmp_path / "r" / ".claude"
    q.mkdir(parents=True)
    state = q / "paths-forward.json"
    wps = [
        {"symbol": "W1", "title": "flag exists", "status": "blocked", "blocked_on": ["nemik-witnesses"],
         "blocked_kind": "agent", "witness": f'input.file["{flag}"].exists'},
        {"symbol": "W2", "title": "never", "status": "blocked", "blocked_on": ["nemik-witnesses"],
         "blocked_kind": "agent", "witness": f'input.file["{tmp_path}/nope"].exists'},
    ]
    state.write_text(json.dumps({"version": 1, "project_root": str(tmp_path / "r"), "counter": 2,
                                 "waypoints": wps, "residue": []}))
    monkeypatch.setattr(sys, "argv", ["nemik-witnesses", "--root", str(tmp_path), "--apply"])
    witnesses.main()
    out = capsys.readouterr().out
    assert "WITNESS r:W1 true" in out and "WITNESS r:W2 false" in out
    after = {w["symbol"]: w for w in json.loads(state.read_text())["waypoints"]}
    assert after["W1"]["status"] == "done" and "witness held" in after["W1"]["evidence"]
    assert after["W2"]["status"] == "blocked"


def _serve(monkeypatch, routes: dict) -> None:
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            body = routes[u.path](parse_qs(u.query))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setenv("NEMIK_VMALERT_URL", base)
    monkeypatch.setenv("NEMIK_VM_URL", base)


def test_alert_and_promql_witnesses(monkeypatch) -> None:
    alerts = [{"name": "Trace", "state": "firing", "labels": {"repo": "a"}},
              {"name": "Trace", "state": "pending", "labels": {"repo": "b"}}]
    _serve(monkeypatch, {
        "/api/v1/alerts": lambda q: {"status": "success", "data": {"alerts": alerts}},
        "/api/v1/query": lambda q: {"status": "success", "data": {"result": (
            [{"value": [0, "3"]}] if q["query"] == ['kube_job_status_succeeded{job_name="t"}'] else [])}},
    })
    assert witness('input.alert["Trace{repo=\\"a\\"}"].state == "firing"')[0] == "true"
    assert witness('input.alert["Trace{repo=\\"b\\"}"].state == "firing"')[0] == "false"
    assert witness('input.alert["Other"].state == "inactive"')[0] == "true"
    assert witness('input.promql["kube_job_status_succeeded{job_name=\\"t\\"}"].values[0] > 0')[0] == "true"
    assert witness('input.promql["absent_metric"].empty')[0] == "true"


def test_unset_endpoint_is_undefined(monkeypatch) -> None:
    monkeypatch.delenv("NEMIK_VM_URL", raising=False)
    assert witness('input.promql["up"].empty')[0] == "undefined"
