# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W78: render the web view in headless Chromium and check that no label is covered.

No waypoint's label may be covered by another waypoint's shape (the operator's occlusion report,
nemik:W77).
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import sync_playwright

VIEWPORT = (1400, 900)
LOADED = "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0"
NODES = 65


def _queue(root: Path, repo: str, n: int) -> None:
    d = root / repo / ".claude"
    d.mkdir(parents=True)
    wps: list[dict[str, object]] = [
        {
            "symbol": f"W{i}",
            "title": f"item {i}",
            "status": "ready" if i % 3 else "blocked",
            "blocked_on": [f"W{i - 1}"] if i % 3 == 0 else [],
            "blocked_kind": "agent" if i % 3 == 0 else None,
            "enables": [f"W{i + 1}"] if i % 4 == 1 and i < n else [],
        }
        for i in range(1, n + 1)
    ]
    body: dict[str, object] = {
        "version": 1,
        "project_root": str(root / repo),
        "counter": n,
        "waypoints": wps,
        "residue": [],
    }
    (d / "paths-forward.json").write_text(json.dumps(body))


@pytest.fixture()
def server(tmp_path: Path) -> Iterator[str]:
    _queue(tmp_path, "alpha", 40)
    _queue(tmp_path, "beta", 25)
    # nemik:W1060: the server binds its own port and says so (webpage.served), and a server that
    # dies before it listens fails here with its stderr, not after a wait for a clock.
    with webpage.served(root=tmp_path) as url:
        yield url


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


BOXES = """() => {
  const units = cy.nodes(".repo, .actor").filter(n => n.visible());
  const hit = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
  const out = [];
  units.forEach(a => units.forEach(b => {
    if (a.id() < b.id() && hit(a.boundingBox(), b.boundingBox())) out.push(a.id() + " x " + b.id());
  }));
  return out;
}"""


def test_labels_are_not_covered_by_other_nodes(server: str) -> None:
    """Labels are not covered by other nodes."""
    with sync_playwright() as p:
        # nemik:W99: Bazel hands a pinned headless shell as $NEMIK_CHROMIUM; launched_page uses it.
        # nemik:W1177: the wait is webpage.load's, bounded and watching the page, not timeout=0.
        browser, page = webpage.launched_page(p, server, LOADED, VIEWPORT)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        overlaps = webpage.evaluate_value(page, OVERLAPS)
        boxes = webpage.evaluate_value(page, BOXES)
        browser.close()
    assert errors == []
    assert overlaps == [NODES, []]  # every node drawn, and no label under another node
    assert (
        boxes == []
    )  # nemik:W117: rows offset toward their neighbours must not overlap
