# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1140: a watched page has no wall-clock deadline on its actions or its navigations."""

import webpage


class RecordingPage:
    """A page that remembers the deadlines it was given and the scripts it was handed."""

    def __init__(self) -> None:
        """Start with no deadline set and no script installed."""
        self.action: float | None = None
        self.navigation: float | None = None
        self.scripts: list[str] = []

    def add_init_script(self, script: str) -> None:
        """Remember an init script."""
        self.scripts.append(script)

    def goto(self, url: str) -> None:
        """Ignore a navigation."""

    def wait_for_function(self, expression: str, *, timeout: float) -> None:
        """Ignore a wait."""

    def evaluate(self, expression: str) -> None:
        """Ignore an evaluation."""

    def set_default_timeout(self, timeout: float) -> None:
        """Remember the action deadline."""
        self.action = timeout

    def set_default_navigation_timeout(self, timeout: float) -> None:
        """Remember the navigation deadline."""
        self.navigation = timeout


def test_watch_takes_the_wall_clock_off_actions_and_navigations() -> None:
    """Playwright reads 0 as no deadline; a default of 30 s failed a click under host load."""
    page = RecordingPage()
    webpage.watch(page)
    assert page.action == 0
    assert page.navigation == 0


def test_watch_still_installs_the_failed_resource_record() -> None:
    """Removing the deadlines does not drop the records watch always installed."""
    page = RecordingPage()
    webpage.watch(page)
    assert any("__failed" in script for script in page.scripts)
