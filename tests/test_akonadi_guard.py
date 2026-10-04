"""nemik:W193 (luthen-observability:W299): the Akonadi helper never starts Akonadi.

Two akonadi_control core dumps (2026-10-02 and 2026-10-03, both in claude-nemik-*.scope) matched
moments this helper ran with no session bus. The helper now refuses first. It is a host build
(./setup.sh), so the test skips where the binary is not built (the Bazel sandbox, the image).
"""

import os
import subprocess

import pytest

from nemik.vtodo import DEFAULT_HELPER


@pytest.mark.skipif(not DEFAULT_HELPER.exists(), reason="the Akonadi helper is a host build")
def test_helper_refuses_without_a_session_bus() -> None:
    env = {"HOME": os.environ.get("HOME", "/"), "PATH": "/usr/bin:/bin"}  # no D-Bus session, no display
    r = subprocess.run([str(DEFAULT_HELPER), "--list", "x"], input=b"", capture_output=True, env=env, timeout=30, check=False)
    assert r.returncode == 2 and b"refusing to start it" in r.stdout, r
