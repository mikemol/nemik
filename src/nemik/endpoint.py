# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""endpoint: where a witness observer finds its backend, with no hand-set environment (W227).

The promql and alert observers read VictoriaMetrics and vmalert. The address is declared once,
in luthen-observability's endpoints.json, and `checks.endpoints_query --side host <name>` prints
it. An environment variable still wins (a test, a laptop, another cluster); with none set, this
asks that tool in the sibling checkout, so a witnessed waypoint can close from a timer with no
wrapper.

A missing checkout, a tool that fails or prints something else, and a slow answer are all
`None`: the observer then reports "cannot observe", never a guessed address.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from nemik.check import default_root

LUTHEN = "luthen-observability"
QUERY_TIMEOUT_SECONDS = 10
PORT_NAMES = {
    "NEMIK_VM_URL": "vmsingle-http",
    "NEMIK_VMALERT_URL": "vmalert-http",
}


def declared_base(name: str, root: Path) -> str | None:
    """Return http://<address> for the port `name` as luthen's endpoints_query prints it."""
    checkout = root / LUTHEN
    if not (checkout / "checks" / "endpoints_query.py").is_file():
        return None
    try:
        done = subprocess.run(
            [sys.executable, "-m", "checks.endpoints_query", "--side", "host", name],
            capture_output=True,
            text=True,
            check=False,
            cwd=checkout,
            env={**os.environ, "PYTHONPATH": str(checkout)},
            timeout=QUERY_TIMEOUT_SECONDS,
        )
        answer: object = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0 or not isinstance(answer, dict):
        return None
    address = answer.get("address")
    if answer.get("state") != "answered" or not address:
        return None
    return f"http://{address}"


def export_defaults() -> list[str]:
    """Set each unset backend variable from luthen's declaration; return the ones it set."""
    exported: list[str] = []
    for env, name in PORT_NAMES.items():
        if os.environ.get(env):
            continue
        base = declared_base(name, default_root())
        if base is not None:
            os.environ[env] = base
            exported.append(env)
    return exported
