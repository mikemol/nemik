# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""witnesses_cli: the `nemik-witnesses` entry point that finds its own backends (W227).

`nemik.witnesses` reads VictoriaMetrics and vmalert through NEMIK_VM_URL and
NEMIK_VMALERT_URL and reports every promql or alert witness as "undefined" when they are unset,
and nothing set them. This entry point fills each unset one from luthen-observability's
declaration (nemik.endpoint) and then runs the unchanged `witnesses.main`. A variable already in
the environment is never overwritten.
"""

from __future__ import annotations

from nemik import endpoint, witnesses


def main(argv: list[str] | None = None) -> None:
    """Export the default backend addresses, then run nemik-witnesses."""
    endpoint.export_defaults()
    witnesses.main(argv)
