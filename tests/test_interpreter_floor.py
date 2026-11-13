# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2161: the image runs an interpreter at 3.14.7 or newer with the generational collector.

tools/interpreter_floor.py holds the rule and the Containerfile runs it after `uv sync`; these tests
hold the rule's two arms apart (the patch floor and the collector, read by its behaviour) and hold
the Containerfile to a digest-pinned interpreter, a digest-pinned uv, no download of another
interpreter, and the check actually running. The suite itself runs on the bazel toolchain's own
interpreter (nemik:W2162), so it does not assert that interpreter passes, only that main() agrees
with the rule for it.
"""

import gc
import re
import sys
from pathlib import Path

from interpreter_floor import FLOOR, main, problems

HERE = Path(__file__).absolute().parents[1]
CONTAINERFILE = (HERE / "Containerfile").read_text(encoding="utf-8")
GENERATIONAL = (2000, 10, 10)
INCREMENTAL = (2000, 10, 0)
DIGEST = r"@sha256:[0-9a-f]{64}"
BOTH = 2


def test_a_floor_patch_with_the_generational_collector_passes() -> None:
    """Pass 3.14.7 and a later patch with the generational collector."""
    assert problems(FLOOR, GENERATIONAL, "/usr/local/bin/python3") == []
    assert problems((3, 14, 9), GENERATIONAL, "/usr/local/bin/python3") == []


def test_the_pod_s_interpreter_fails_on_both_counts() -> None:
    """Fail 3.14.2 with the incremental collector, naming the patch and the collector."""
    said = problems((3, 14, 2), INCREMENTAL, "/app/.venv/bin/python")
    assert len(said) == BOTH
    assert "below 3.14.7" in said[0]
    assert "incremental collector" in said[1]


def test_the_collector_is_read_by_behaviour_not_by_patch_number() -> None:
    """Fail a newer patch with the incremental collector, and an old patch for its number alone."""
    newer = problems((3, 14, 9), INCREMENTAL, "/usr/local/bin/python3")
    assert len(newer) == 1
    assert "incremental collector" in newer[0]
    older = problems((3, 14, 6), GENERATIONAL, "/usr/local/bin/python3")
    assert len(older) == 1
    assert "below 3.14.7" in older[0]


def test_main_agrees_with_the_rule_for_this_interpreter() -> None:
    """Return 0 exactly when the rule passes this interpreter's own version and collector."""
    info = sys.version_info
    version = (info.major, info.minor, info.micro)
    expected = problems(version, gc.get_threshold(), sys.executable)
    assert main() == (1 if expected else 0)


def test_the_containerfile_pins_the_interpreter_and_uv_by_digest() -> None:
    """Pin the python image at 3.14.7 or newer and the uv image, each by digest."""
    python = re.search(r"^ARG PYTHON=(\S+)$", CONTAINERFILE, re.MULTILINE)
    uv = re.search(r"^ARG UV=(\S+)$", CONTAINERFILE, re.MULTILINE)
    assert python is not None
    assert uv is not None
    tag = re.search(r"python:3\.14\.(\d+)-", python.group(1))
    assert tag is not None, "the python image names its 3.14 patch"
    assert int(tag.group(1)) >= FLOOR[2]
    assert re.search(DIGEST + "$", python.group(1))
    assert re.search(DIGEST + "$", uv.group(1))
    assert "ARG BASE=" not in CONTAINERFILE, "no floating base image arg"


def test_the_image_never_fetches_another_interpreter_and_runs_the_check() -> None:
    """Stop uv downloading a Python, and run the floor check right after the dependency sync."""
    assert "UV_PYTHON_DOWNLOADS=never" in CONTAINERFILE
    assert "UV_PYTHON_PREFERENCE=only-system" in CONTAINERFILE
    sync = CONTAINERFILE.index("RUN uv sync --frozen --no-dev")
    check = CONTAINERFILE.index("RUN /app/.venv/bin/python tools/interpreter_floor.py")
    assert sync < check
