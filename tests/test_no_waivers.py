"""nemik:W523: no suppression directive anywhere in nemik's Python, held by the gate.

The house rule (mtools): a finding is fixed or the rule is changed in the one reviewed place, never waived
on a line. The edit hook enforces it on the lines an agent touches; this holds the whole tree, so a
waiver that arrives by any other route (a merge, a hand edit, a copied snippet) fails the gate too.
The patterns are written from pieces so that this file holds none of the directives it forbids.
"""

import re
from pathlib import Path

import nemik

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    "no" + "qa",
    r"type:\s*ig" + "nore",
    "no" + "sec",
    r"pragma:\s*no\s*cover",
    r"pylint:\s*dis" + "able",
    r"mypy:\s*ig" + r"nore-errors",
    r"fmt:\s*(?:off|skip)",
    r"isort:\s*skip",
]
DIRECTIVE = re.compile(r"#\s*(?:" + "|".join(FORBIDDEN) + ")", re.IGNORECASE)


def _sources() -> list[Path]:
    package = Path(nemik.__file__).resolve().parent
    return sorted(
        [
            *package.rglob("*.py"),
            *(ROOT / "tests").glob("*.py"),
            *(ROOT / "tools").glob("*.py"),
            *(ROOT / "checks").glob("*.py"),
        ]
    )


def test_no_python_file_waives_a_check() -> None:
    sources = _sources()
    assert len(sources) > 100, "the scan found almost no files"
    found = [
        f"{path.name}:{n}: {line.strip()[:90]}"
        for path in sources
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if DIRECTIVE.search(line)
    ]
    assert not found, (
        "a waiver is a finding left unfixed; fix it or change the rule:\n"
        + "\n".join(found)
    )


def test_the_detector_sees_each_directive() -> None:
    samples = [
        "x = 1  # " + "no" + "qa: E501",
        "y = f()  # type: " + "ig" + "nore[arg-type]",
        "z = g()  # " + "no" + "sec",
        "if a:  # pragma: no " + "cover",
        "# pylint: " + "dis" + "able=all",
        "# fmt: " + "off",
    ]
    assert all(DIRECTIVE.search(s) for s in samples)
    assert not DIRECTIVE.search("# a comment about noise and ignoring nothing")
