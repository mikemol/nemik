"""nemik:W513: a console script is declared in every registry it belongs in, and a gap is named at once.

nemik-static (W502) was refused by three checks in turn, one gate run each: the BUILD console_scripts
table, the skill's command table, and the workflows registry. Each of those still has its own test; this
one reads pyproject's [project.scripts] against all of them together, so adding a command is one pass
instead of one failure per registry.
"""

import tomllib
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _gaps(script: str, build: str, skill: str, workflows: str) -> list[str]:
    gaps = []
    if f'"{script}":' not in build:
        gaps.append("BUILD.bazel console_scripts")
    if f"`{script}" not in skill:
        gaps.append("skills/nemik/SKILL.md commands table")
    if f'"{script}"' not in workflows:
        gaps.append("src/nemik/data/workflows.toml (a workflow step or [reference])")
    return gaps


def test_every_nemik_command_is_declared_in_every_registry() -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    build = (ROOT / "BUILD.bazel").read_text()
    skill = (ROOT / "skills" / "nemik" / "SKILL.md").read_text()
    workflows = files("nemik.data").joinpath("workflows.toml").read_text()
    missing = {
        s: gaps
        for s in scripts
        if s.startswith("nemik-") and (gaps := _gaps(s, build, skill, workflows))
    }
    assert not missing, "declare each new command everywhere at once:\n" + "\n".join(
        f"  {s}: {', '.join(g)}" for s, g in sorted(missing.items())
    )


def test_a_command_missing_from_a_registry_is_named_with_all_its_gaps() -> None:
    assert _gaps("nemik-new", '"nemik-old": "x"', "`nemik-old`", '"nemik-old"') == [
        "BUILD.bazel console_scripts",
        "skills/nemik/SKILL.md commands table",
        "src/nemik/data/workflows.toml (a workflow step or [reference])",
    ]
    assert _gaps("nemik-old", '"nemik-old": "x"', "`nemik-old`", '"nemik-old"') == []
