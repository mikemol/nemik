# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W94: every nemik command imports this package, so an editable install is flagged here.

An editable install runs the working tree, not what was installed: a CLI then behaves as whatever
is checked out at the moment, and Bazel's sandbox cannot see it. The install is meant to be a real
package in the repo's own .venv (operator ruling, nemik:W93).
"""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, distribution
from typing import cast


def editable_install() -> bool:
    """Say whether the installed `nemik` distribution records itself as editable.

    Returns:
        True when PEP 610's direct_url.json marks the install editable, else False (including
        when the distribution is not installed).

    """
    try:
        text = distribution("nemik").read_text("direct_url.json")
    except PackageNotFoundError:
        return False
    if not text:
        return False
    # PEP 610: a JSON object whose `dir_info` object carries the `editable` flag; anything else is
    # not an editable install, and each step is narrowed from what the next one reads.
    loaded = cast("object", json.loads(text))
    if not isinstance(loaded, dict):
        return False
    info = cast("dict[str, object]", loaded).get("dir_info")
    if not isinstance(info, dict):
        return False
    return bool(cast("dict[str, object]", info).get("editable"))


if editable_install():
    sys.stderr.write(
        "nemik: WARNING running from an editable install; "
        "use the built venv: ./setup.sh (bazel build //:.venv)\n"
    )
