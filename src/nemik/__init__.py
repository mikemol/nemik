"""nemik:W94: every nemik command imports this package, so this is where an editable install is flagged.

An editable install runs the working tree, not what was installed: a CLI then behaves as whatever
is checked out at the moment, and Bazel's sandbox cannot see it. The install is meant to be a real
package in the repo's own .venv (operator ruling, nemik:W93).
"""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, distribution


def editable_install() -> bool:
    """True when the installed `nemik` distribution records itself as editable (PEP 610 direct_url.json)."""
    try:
        text = distribution("nemik").read_text("direct_url.json")
    except PackageNotFoundError:
        return False
    if not text:
        return False
    return bool(json.loads(text).get("dir_info", {}).get("editable"))


if editable_install():
    print("nemik: WARNING running from an editable install; install it as a package: uv sync --no-editable",
          file=sys.stderr)
