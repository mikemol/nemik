# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W660: the image's test stage stamps the time before and after each long step.

Forgejo cancelled the image build 20:00 after each start and the run log could not say which step
it was in. Each long step now prints a UTC stamp when it starts and when it ends, so the next
cancelled run's log names the step.
"""

from pathlib import Path

CONTAINERFILE = Path(__file__).resolve().parents[1] / "Containerfile"


def test_the_deps_and_pytest_steps_stamp_their_start_and_end() -> None:
    """Both long steps print a UTC stamp on entry and on exit."""
    text = CONTAINERFILE.read_text()
    for step in ("deps", "pytest"):
        for edge in ("start", "end"):
            assert f"test stage: {step} {edge} %FT%TZ" in text, f"{step} {edge}"


def test_the_pytest_step_is_stamped_around_the_run() -> None:
    """The stamps bracket pytest, and the tested marker is written after the end stamp."""
    text = CONTAINERFILE.read_text()
    start = text.index("pytest start")
    run = text.index(".venv/bin/pytest -q")
    end = text.index("pytest end")
    marker = text.index("touch /app/.tested")
    assert start < run < end < marker
