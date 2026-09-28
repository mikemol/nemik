"""The nemik skill (skills/nemik/SKILL.md, linked into ~/.claude/skills) stays current: adding a
command or a check rule without documenting it fails here (operator 2026-09-28: "a skill that
remains up-to-date on how to use nemik")."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/nemik/SKILL.md").read_text()


def test_every_nemik_command_is_documented() -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    missing = [s for s in scripts if s.startswith("nemik-") and f"`{s}" not in SKILL]
    assert not missing, f"skills/nemik/SKILL.md does not document {missing}"


def test_every_check_shape_is_documented() -> None:
    shapes = re.findall(r"^nemik:(\w+Shape) a sh:NodeShape", (ROOT / "src/nemik/data/shapes.ttl").read_text(), re.M)
    assert shapes
    missing = [s for s in shapes if f"`{s}`" not in SKILL]
    assert not missing, f"skills/nemik/SKILL.md does not document {missing}"
