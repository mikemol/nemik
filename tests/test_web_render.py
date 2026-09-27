"""nemik:W78: render the web view in headless Chromium and check that no waypoint's label is covered
by another waypoint's shape (the operator's occlusion report, nemik:W77)."""

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

import installed

sync_api = pytest.importorskip("playwright.sync_api")


def _queue(root: Path, repo: str, n: int) -> None:
    d = root / repo / ".claude"
    d.mkdir(parents=True)
    wps = [{"symbol": f"W{i}", "title": f"item {i}", "status": "ready" if i % 3 else "blocked",
            "blocked_on": [f"W{i - 1}"] if i % 3 == 0 else [], "blocked_kind": "agent" if i % 3 == 0 else None,
            "enables": [f"W{i + 1}"] if i % 4 == 1 and i < n else []} for i in range(1, n + 1)]
    (d / "paths-forward.json").write_text(json.dumps(
        {"version": 1, "project_root": str(root / repo), "counter": n, "waypoints": wps, "residue": []}))


@pytest.fixture
def server(tmp_path):
    _queue(tmp_path, "alpha", 40)
    _queue(tmp_path, "beta", 25)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = installed.popen("nemik-serve", "--root", str(tmp_path), "--port", str(port),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/"
    proc.terminate()
    proc.wait()


OVERLAPS = """() => {
  const ns = cy.nodes("[symbol]").filter(n => n.visible());
  const hit = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
  const out = [];
  ns.forEach(n => {
    const label = n.boundingBox({ includeNodes: false, includeLabels: true, includeOverlays: false });
    ns.forEach(m => {
      if (m !== n && hit(label, m.boundingBox({ includeLabels: false, includeOverlays: false })))
        out.push(n.data("label") + " under " + m.data("label"));
    });
  });
  return [ns.length, out];
}"""


def test_labels_are_not_covered_by_other_nodes(server) -> None:
    with sync_api.sync_playwright() as p:
        try:
            # nemik:W99: Bazel hands a pinned headless shell as $NEMIK_CHROMIUM; the host uses Playwright's cache.
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=20000)
        count, overlaps = page.evaluate(OVERLAPS)
        browser.close()
    assert errors == []
    assert count == 65
    assert overlaps == []
