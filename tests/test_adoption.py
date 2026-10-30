# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1179: adoption judges a parsed pyproject, and check reads the repo for it."""

from pathlib import Path

from nemik import adoption
from nemik.check import adoption_state

PACKAGE = adoption.PACKAGE


def _doc(**tables: object) -> dict[str, object]:
    return dict(tables)


def _queue(root: Path, pyproject: str | None) -> Path:
    root.mkdir()
    claude = root / ".claude"
    claude.mkdir()
    if pyproject is not None:
        (root / "pyproject.toml").write_text(pyproject)
    return claude / "paths-forward.json"


def test_names_are_the_leading_run_lower_cased_with_hyphens() -> None:
    """A requirement's name is its leading run, normalised; non-strings and empties are skipped."""
    specs = ["  Mikemol_PathsForward >= 1", "rdflib", "", 7, "==bad"]
    assert adoption.names(specs) == {"mikemol-pathsforward", "rdflib"}
    assert adoption.names("not a list") == set()


def test_a_dependency_is_found_in_any_of_the_three_places() -> None:
    """Project, optional and dependency-group dependencies all count; others do not."""
    dependencies = {"dependencies": [PACKAGE + " @ git+x"]}
    optional = {"optional-dependencies": {"dev": [PACKAGE]}}
    assert adoption.declares(_doc(project=dependencies))
    assert adoption.declares(_doc(project=optional))
    assert adoption.declares(_doc(**{"dependency-groups": {"dev": [PACKAGE]}}))
    assert not adoption.declares(_doc(project={"dependencies": ["rdflib"]}))
    assert not adoption.declares(_doc())


def test_the_package_owner_is_the_project_named_for_it() -> None:
    """Only a project named for the package owns it; a non-table project owns nothing."""
    assert adoption.owns(_doc(project={"name": PACKAGE}))
    assert not adoption.owns(_doc(project={"name": "nemik"}))
    assert not adoption.owns(_doc(project="not a table"))


def test_state_is_read_from_the_repo_tree(tmp_path: Path) -> None:
    """No pyproject, a bad one, one without the package and one with it read four ways."""
    bare = '[project]\nname = "x"\ndependencies = ["rdflib"]\n'
    wired = f'[project]\nname = "x"\ndependencies = ["{PACKAGE}"]\n'
    cases = [
        ("none", None, "no-pyproject"),
        ("bad", "= not toml", "missing"),
        ("without", bare, "missing"),
        ("with", wired, "declared"),
    ]
    for name, text, want in cases:
        assert adoption_state(_queue(tmp_path / name, text)) == want, name


def test_a_queue_outside_a_claude_directory_is_unobservable(tmp_path: Path) -> None:
    """An export with no repo tree beside it cannot be judged."""
    assert adoption_state(tmp_path / "paths-forward.json") == "unobservable"


def test_a_repo_holding_the_package_tree_is_its_owner(tmp_path: Path) -> None:
    """A repo with a pyproject for the package one level down ships it."""
    queue = _queue(tmp_path / "repo", None)
    sub = tmp_path / "repo" / "pathsforward"
    sub.mkdir()
    (sub / "pyproject.toml").write_text(f'[project]\nname = "{PACKAGE}"\n')
    assert adoption_state(queue) == "owner"
