# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2026: the architecture claims read nemik imports from the syntax tree, in every form.

The first finder was a regex for `from nemik.x import y`, which cannot see `from nemik import x`:
adapter-is-the-foundation-layer passed for weeks while adapter.py imported five nemik modules that
way. These plant each form and hold the two finders (all imports, and import-time imports) to it.
The finders are private to checks/claims.py (every public function there is a registered witness),
so they are read from the loaded module's namespace.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[1]


def _finder(name: str) -> Callable[[str], set[str]]:
    """Load checks/claims.py, a script and not a package, and take one of its finders.

    Returns:
        The finder function the name gives.

    """
    spec = importlib.util.spec_from_file_location(
        "claims", ROOT / "checks" / "claims.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    finder: Callable[[str], set[str]] = getattr(module, name)
    return finder


def _all(text: str) -> set[str]:
    """Run the all-imports finder on a planted text.

    Returns:
        The nemik modules it names.

    """
    return _finder("_imports_nemik")(text)


def _at_import(text: str) -> set[str]:
    """Run the import-time finder on a planted text.

    Returns:
        The nemik modules it names.

    """
    return _finder("_import_time_nemik")(text)


def test_the_dotted_form_is_seen() -> None:
    """`from nemik.a import b` names a."""
    assert _all("from nemik.a import b\n") == {"a"}


def test_the_no_dot_forms_are_seen() -> None:
    """MUTANT: the regex finder saw none of these; each name is a module."""
    assert _all("from nemik import a\n") == {"a"}
    assert _all("from nemik import a, b\n") == {"a", "b"}
    assert _all("from nemik import (\n    a,\n    b as c,\n)\n") == {"a", "b"}


def test_the_plain_import_form_is_seen() -> None:
    """`import nemik.a` and `import nemik.a as x` name a; `import nemik` names nothing."""
    assert _all("import nemik.a\n") == {"a"}
    assert _all("import nemik.a as x\n") == {"a"}
    assert _all("import nemik\n") == set()


def test_an_import_inside_a_function_or_a_try_is_seen() -> None:
    """The all-imports finder does not care how deep the statement sits."""
    text = (
        "def f():\n    from nemik import a\n\n"
        "try:\n    import nemik.b\nexcept ImportError:\n    pass\n"
    )
    assert _all(text) == {"a", "b"}


def test_a_docstring_or_comment_that_looks_like_an_import_is_not() -> None:
    """The finder reads statements, not text."""
    text = '"""from nemik import a"""\n# from nemik.b import c\nx = "import nemik.d"\n'
    assert _all(text) == set()


def test_another_package_and_a_relative_import_are_not_nemik() -> None:
    """`from other import nemik_thing`, `from .a import b` and nemik-prefixed names are not it."""
    assert _all("from other import nemik\nfrom .a import b\nimport nemikx.y\n") == set()


def test_the_import_time_finder_leaves_out_what_does_not_run_at_import() -> None:
    """A function-local import and a TYPE_CHECKING body are edges for _all, not at import."""
    text = (
        "from typing import TYPE_CHECKING\n"
        "from nemik import a\n"
        "if TYPE_CHECKING:\n    from nemik import typed\nelse:\n    from nemik import real\n"
        "try:\n    from nemik import t\nexcept ImportError:\n    from nemik import e\n"
        "def f():\n    from nemik import lazy\n"
        "class C:\n    import nemik.inner\n"
    )
    assert _at_import(text) == {"a", "real", "t", "e"}
    assert _all(text) == {"a", "typed", "real", "t", "e", "lazy", "inner"}


def test_every_statement_that_runs_its_body_at_import_is_entered() -> None:
    """MUTANT: a finder that skipped a block form would lose an edge, and a cycle with it."""
    text = (
        "async with x:\n    from nemik import aw\n"
        "async for i in x:\n    from nemik import af\nelse:\n    from nemik import afe\n"
        "for i in x:\n    pass\nelse:\n    from nemik import fe\n"
        "while x:\n    pass\nelse:\n    from nemik import we\n"
        "match x:\n    case 1:\n        from nemik import m1\n"
        "    case _:\n        from nemik import m2\n"
        "try:\n    pass\nexcept* E:\n    from nemik import star\n"
    )
    assert _at_import(text) == {"aw", "af", "afe", "fe", "we", "m1", "m2", "star"}


def test_if_not_type_checking_runs_its_body_and_not_its_else() -> None:
    """`if not TYPE_CHECKING:` runs at import; the else of it is the type-only branch."""
    text = (
        "from typing import TYPE_CHECKING\n"
        "if not TYPE_CHECKING:\n    from nemik import real\n"
        "else:\n    from nemik import typed\n"
        "import typing\n"
        "if not typing.TYPE_CHECKING:\n    from nemik import real2\n"
        "else:\n    from nemik import typed2\n"
    )
    assert _at_import(text) == {"real", "real2"}
    assert _all(text) == {"real", "typed", "real2", "typed2"}


def test_the_real_adapter_is_seen_with_its_no_dot_imports() -> None:
    """adapter.py imports its leaf modules the no-dot way: the claim would pass blind without it."""
    seen = _all((ROOT / "src" / "nemik" / "adapter.py").read_text(encoding="utf-8"))
    assert {"vocab", "warrants", "editverbs"} <= seen
