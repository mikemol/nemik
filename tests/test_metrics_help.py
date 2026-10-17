# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W531: nemik-metrics prints well-formed Prometheus text, HELP and TYPE per family."""

import re
from pathlib import Path

import pytest

from nemik.metrics import HELP, main, with_help

FLEET = Path(__file__).parent / "fixtures" / "fleet"
SAMPLE = re.compile(
    r'^([a-z_:][a-z0-9_:]*)(\{([a-z_][a-z0-9_]*="[^"]*",?)*\})? -?[0-9.]+(e[+-]?[0-9]+)?$'
)


def _exposition(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> list[str]:
    """Run nemik-metrics over the fixture fleet.

    Args:
        capsys: pytest's output capture.
        tmp_path: A scratch directory for the (absent) prompt spool.

    Returns:
        The printed lines.

    """
    main(["--root", str(FLEET), "--spool", str(tmp_path / "none")])
    return capsys.readouterr().out.splitlines()


def test_every_family_has_help_then_type_and_every_sample_parses(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """HELP precedes TYPE for each family, and each sample line is name{labels} value."""
    lines = _exposition(capsys, tmp_path)
    seen: set[str] = set()
    for at, line in enumerate(lines):
        words = line.split()
        if line.startswith("# TYPE"):
            assert lines[at - 1] == f"# HELP {words[2]} {HELP[words[2]]}", line
            seen.add(words[2])
        elif not line.startswith("#"):
            assert SAMPLE.match(line), line
            assert line.split("{")[0].split(" ")[0] in seen, line
    assert seen


def test_a_family_without_help_text_is_left_bare() -> None:
    """with_help only adds text it has; the test above is what refuses a bare family."""
    assert with_help(["# TYPE nemik_unknown gauge"]) == ["# TYPE nemik_unknown gauge"]
