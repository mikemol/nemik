# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W669: the Wake panel names the repos with work that are not awake, from luthen's series."""

import json
import os
import time
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

READY = "() => document.getElementById('wake').innerText.length > 5"
SHOWN = "() => document.getElementById('wake').innerText"


def _absolute(path: str) -> str:
    """Make a path absolute.

    Args:
        path: A path, possibly relative to the test's working directory.

    Returns:
        The absolute path.

    """
    return str(Path(path).resolve())


def _snapshot(path: Path) -> Path:
    """Write a fresh snapshot: gabion asleep, life idle, mtools awake.

    Args:
        path: Where to write it.

    Returns:
        The path.

    """
    now = int(time.time())
    hour = 3600
    body = {
        "version": 1,
        "as_of": now - 30,
        "liveness": {
            "gabion": {
                "verdict": "dormant",
                "history": [[now - 2 * hour, "ok"], [now - hour, "dormant"]],
            },
            "life": {"verdict": "stale", "history": [[now - hour, "stale"]]},
            "mtools": {"verdict": "ok", "history": [[now - hour, "ok"]]},
        },
        "tokens": [],
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _wake_text(series: Path | None) -> str:
    """Read the Wake panel's text once the page has drawn it.

    Args:
        series: The snapshot file the server is given, or None.

    Returns:
        The panel's visible text.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with webpage.served(series) as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=_absolute(exe) if exe else None)
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        webpage.watch(page)
        page.goto(url)
        webpage.until(page, READY)
        text: object = page.evaluate(SHOWN)
        browser.close()
    return str(text)


def test_the_panel_names_the_repos_with_work_that_are_not_awake(tmp_path: Path) -> None:
    """The asleep gabion and idle life hold fixture cards and are named, with their history."""
    text = _wake_text(_snapshot(tmp_path / "series.json"))
    assert "with work, not awake" in text
    assert "gabion" in text
    assert "% of its history" in text


def test_without_a_series_the_panel_draws_no_board() -> None:
    """No --series, no board: the panel is what it was."""
    assert "not awake" not in _wake_text(None)
