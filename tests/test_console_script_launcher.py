# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2137: the generated console script imports only the running interpreter's site-packages.

bazel/venv.bzl writes each entry point from one template. A venv left holding an older
interpreter's lib/pythonX.Y beside the new one (an earlier build in the same output base) must not
put that older directory on sys.path: the 3.14 pilot's test_layout served nemik from a stale
lib/python3.13 that had no nemik/_typing.py. The test renders the template into a temporary venv
and runs it with the interpreter that runs the test, so the pilot's venv covers the 3.14 case and
a 3.13 host covers 3.13.
"""

import re
import sys
from pathlib import Path

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]
MAJOR, MINOR = sys.version_info.major, sys.version_info.minor
OWN = f"python{MAJOR}.{MINOR}"
STALE = [
    f"python{MAJOR}.{MINOR + 1}",
    f"python{MAJOR}.{MINOR - 1}",
    f"python{MAJOR}.{MINOR - 5}",
]
GOOD = "def main():\n    print('own')\n    return 0\n"
BAD = "raise RuntimeError('stale sibling imported')\n"
GLOB = (
    'for _libdir in sorted(_site.glob("python*/site-packages")):\n'
    "    if str(_libdir) not in sys.path:\n"
    "        sys.path.insert(0, str(_libdir))\n"
)
FAILS = 1


def _template() -> str:
    """Read the console-script template out of bazel/venv.bzl.

    Returns:
        The template text with its module and function fields still in place.

    """
    text = (ROOT / "bazel" / "venv.bzl").read_text(encoding="utf-8")
    body = re.search(r'_CONSOLE_SCRIPT = """\\\n(.*?)"""', text, re.DOTALL)
    assert body is not None
    return body.group(1)


def _render(template: str) -> str:
    """Fill the template's two fields so the entry point imports sitecheck.main.

    Args:
        template: The template text, fields still in place.

    Returns:
        The runnable entry-point source.

    """
    return template.replace("{module}", "sitecheck").replace("{function}", "main")


def _run(root: Path, dirs: dict[str, str], script: str) -> tuple[int, str]:
    """Lay out a venv with one sitecheck.py per lib directory and run its entry point.

    Args:
        root: An empty directory to build the venv in.
        dirs: The lib directory names mapped to the source of the sitecheck module each holds.
        script: The rendered entry point.

    Returns:
        The exit code and the output of the run.

    """
    for name, source in dirs.items():
        pkg = root / "lib" / name / "site-packages"
        pkg.mkdir(parents=True)
        (pkg / "sitecheck.py").write_text(source, encoding="utf-8")
    entry = root / "bin" / "entry"
    entry.parent.mkdir()
    entry.write_text(script, encoding="utf-8")
    done = capture([sys.executable, str(entry)])
    return done.returncode, done.stdout + done.stderr


def test_the_own_directory_alone_is_imported(tmp_path: Path) -> None:
    """A venv holding only the running interpreter's directory serves its module."""
    code, out = _run(tmp_path, {OWN: GOOD}, _render(_template()))
    assert code == 0
    assert "own" in out


def test_a_stale_sibling_directory_is_not_imported(tmp_path: Path) -> None:
    """Older and newer sibling directories hold a module that raises; the own one is used."""
    dirs = {OWN: GOOD, **dict.fromkeys(STALE, BAD)}
    code, out = _run(tmp_path, dirs, _render(_template()))
    assert code == 0
    assert "own" in out


def test_an_absent_own_directory_is_refused_naming_what_is_there(
    tmp_path: Path,
) -> None:
    """With no directory for this interpreter the entry point exits non-zero, listing the others."""
    dirs = dict.fromkeys(STALE, GOOD)
    code, out = _run(tmp_path, dirs, _render(_template()))
    assert code != 0
    assert all(name in out for name in STALE)


def test_the_glob_over_every_sibling_would_import_the_stale_one(tmp_path: Path) -> None:
    """A mutant restoring the old glob fails the stale-sibling case, so the case discriminates."""
    template = _template()
    start = template.index("# nemik:W2137")
    end = template.index("from {module}")
    mutant = _render(template[:start] + GLOB + "\n" + template[end:])
    dirs = {OWN: GOOD, **dict.fromkeys(STALE, BAD)}
    code, out = _run(tmp_path, dirs, mutant)
    assert code == FAILS
    assert "stale sibling imported" in out
