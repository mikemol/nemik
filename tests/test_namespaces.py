# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1150: two repos declaring one top-level package name are listed, and unread ones named."""

from pathlib import Path

from namespaces import census, declared, report

SINGLE = """\
[project]
name = "x"

[tool.setuptools]
packages = ["tools", "linux_sources.sub"]  # the second belongs to linux_sources
"""
MULTILINE = """\
[tool.setuptools]
packages = [
    "alpha",
    'beta.gamma',
]

[tool.other]
packages = ["not-ours"]
"""


def test_the_declared_names_are_the_top_level_part_of_the_setuptools_packages() -> None:
    """A dotted entry is owned by whoever wins its first part, and a comment is not read."""
    assert declared(SINGLE) == ["linux_sources", "tools"]


def test_a_list_over_several_lines_and_a_package_list_elsewhere() -> None:
    """Only the [tool.setuptools] list counts, over any number of lines and either quote."""
    assert declared(MULTILINE) == ["alpha", "beta"]


def test_a_pyproject_with_no_package_list_declares_nothing() -> None:
    """No list found reads as no names, and the count says so."""
    assert declared('[project]\nname = "x"\n') == []


def _repo(root: Path, name: str, text: str) -> None:
    """Make a repo directory holding a pyproject."""
    (root / name).mkdir()
    (root / name / "pyproject.toml").write_text(text, encoding="utf-8")


def test_a_name_two_repos_declare_is_contested_and_a_hidden_tree_is_skipped(
    tmp_path: Path,
) -> None:
    """The census lists the contested name with both repos, and skips a dot directory."""
    _repo(tmp_path, "a", '[tool.setuptools]\npackages = ["tools", "a_only"]\n')
    _repo(tmp_path, "b", '[tool.setuptools]\npackages = ["tools"]\n')
    _repo(tmp_path, ".gate-wt", '[tool.setuptools]\npackages = ["tools"]\n')
    claims, unread = census(tmp_path)
    assert claims == {"a_only": ["a"], "tools": ["a", "b"]}
    assert not unread
    assert report(claims, unread) == [
        "tools: claimed by a, b",
        "namespaces: 2 names declared, 1 contested",
    ]


def test_a_repo_whose_pyproject_cannot_be_read_is_named_not_counted_absent(
    tmp_path: Path,
) -> None:
    """Undecodable bytes make the claim unknown; the report says so."""
    _repo(tmp_path, "a", '[tool.setuptools]\npackages = ["tools"]\n')
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "pyproject.toml").write_bytes(b"\xff\xfe\x00")
    claims, unread = census(tmp_path)
    assert unread == ["bad"]
    assert report(claims, unread)[-1] == "unread (claims unknown, not absent): bad"
