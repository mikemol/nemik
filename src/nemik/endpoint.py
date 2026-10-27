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

import http.client
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

from nemik.check import default_root

LUTHEN = "luthen-observability"
QUERY_TIMEOUT_SECONDS = 10
VLOGS_TIMEOUT_SECONDS = 30
EXPORT_TIMEOUT_SECONDS = 60
# how far back the ratchet series reach: far more gate runs than one pace window
EXPORT_SINCE = "30d"
VLOGS_LIMIT = 2000  # a ship is ~330 lines; hours of refreshes still fit
PORT_NAMES = {
    "NEMIK_VM_URL": "vmsingle-http",
    "NEMIK_VMALERT_URL": "vmalert-http",
}


def _luthen(
    checkout: Path, module_argv: list[str], timeout: int
) -> subprocess.CompletedProcess[str]:
    """Run `python -m <module> ...` inside luthen's checkout, the one place this module spawns.

    Returns:
        The completed process.

    """
    environ = dict(os.environ)
    environ["PYTHONPATH"] = str(checkout)
    return subprocess.run(
        [sys.executable, "-m", *module_argv],
        capture_output=True,
        text=True,
        check=False,
        cwd=checkout,
        env=environ,
        timeout=timeout,
    )


def declared_base(name: str, root: Path) -> str | None:
    """Return http://<address> for the port `name` as luthen's endpoints_query prints it."""
    checkout = root / LUTHEN
    if not (checkout / "checks" / "endpoints_query.py").is_file():
        return None
    try:
        done = _luthen(
            checkout,
            ["checks.endpoints_query", "--side", "host", name],
            QUERY_TIMEOUT_SECONDS,
        )
        answer: object = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0 or not isinstance(answer, dict):
        return None
    address, state = answer.get("address"), answer.get("state")
    if not isinstance(state, str) or state != "answered":
        return None
    if not isinstance(address, str) or not address:
        return None
    return f"http://{address}"


def vlogs_lines(query: str, root: Path, limit: int = VLOGS_LIMIT) -> list[str]:
    """Run a LogsQL query through luthen's checks.vlogs_query and return its lines (nemik:W774).

    Args:
        query: The LogsQL query.
        root: The directory holding the luthen-observability checkout.
        limit: The most lines to ask for.

    Returns:
        One JSON record per line, as VictoriaLogs prints them.

    Raises:
        OSError: When the checkout is missing, the tool fails, or it outlasts the timeout.

    """
    checkout = root / LUTHEN
    if not (checkout / "checks" / "vlogs_query.py").is_file():
        message = f"no {LUTHEN} checkout with checks/vlogs_query.py under {root}"
        raise OSError(message)
    try:
        done = _luthen(
            checkout,
            ["checks.vlogs_query", "--limit", str(limit), query],
            VLOGS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        message = f"vlogs_query outlasted {VLOGS_TIMEOUT_SECONDS} s"
        raise OSError(message) from error
    if done.returncode != 0:
        message = f"vlogs_query exited {done.returncode}"
        raise OSError(message)
    return done.stdout.splitlines()


def vm_export(match: str, root: Path, since: str = EXPORT_SINCE) -> str:
    """Read the metric store's raw export of a selector, one sample as written per gate run.

    Args:
        match: The series selector, e.g. {__name__="mikemol.ratchet.value"}.
        root: The directory holding the luthen-observability checkout, whose endpoints_query names
            the store's address.
        since: How far back to read, as a relative duration like 30d.

    Returns:
        The export's text, one JSON object per series per line.

    Raises:
        OSError: When the store's address cannot be found, or it cannot be reached or answers badly.

    """
    base = declared_base("vmsingle-http", root)
    if base is None:
        message = f"no vmsingle-http address from the {LUTHEN} checkout under {root}"
        raise OSError(message)
    query = urllib.parse.urlencode({"match[]": match, "start": f"-{since}"})
    connection = http.client.HTTPConnection(
        urllib.parse.urlsplit(base).netloc, timeout=EXPORT_TIMEOUT_SECONDS
    )
    try:
        status, body = _get(connection, f"/api/v1/export?{query}")
    except (http.client.HTTPException, ValueError) as error:
        message = f"the store's export could not be read: {error}"
        raise OSError(message) from error
    finally:
        connection.close()
    if status != http.client.OK:
        message = f"the store's export answered {status}"
        raise OSError(message)
    return body


def _get(connection: http.client.HTTPConnection, target: str) -> tuple[int, str]:
    """GET a path on an open connection.

    Returns:
        (the status code, the body decoded as UTF-8).

    """
    connection.request("GET", target)
    reply = connection.getresponse()
    return reply.status, reply.read().decode("utf-8")


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
