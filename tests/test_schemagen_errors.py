# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: a manifest the old apischema refused is refused by the arena generator too.

tests/fixtures/apischema/apischema-errors.json records what the OLD module did on nine bad
manifests: it raised on every one (KeyError, TypeError, AttributeError or JSONDecodeError).
The replacement raises ValueError for all of them, because the pinned Codon cannot compile
every exception class. What must not happen is the silent output an index of -1 into the
arena would give.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from nemik.schemagen import render

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "apischema" / "apischema-errors.json"
)


def _cases() -> dict[str, dict[str, str]]:
    loaded: object = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return cast("dict[str, dict[str, str]]", loaded)


CASES = _cases()


@pytest.mark.parametrize("name", list(CASES))
def test_a_bad_manifest_is_refused_where_the_old_module_refused_it(name: str) -> None:
    """The old outcome was a raise, and the generator raises ValueError rather than answer."""
    assert CASES[name]["outcome"].startswith("raises ")
    with pytest.raises(ValueError, match="manifest"):
        render(CASES[name]["manifest"])


PACKAGED = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "apischema"
    / "apischema-manifest.json"
)


def test_a_section_that_is_not_an_object_is_refused() -> None:
    """nemik:W2043 D1: a ruler section set to a list was an AttributeError, never a schema."""
    doc = cast(
        "dict[str, dict[str, dict[str, object]]]",
        json.loads(PACKAGED.read_text(encoding="utf-8")),
    )
    doc["files"]["graph.json"]["ruler"] = []
    with pytest.raises(ValueError, match="manifest"):
        render(json.dumps(doc))


def test_text_after_the_document_is_refused() -> None:
    """nemik:W2043 D1: json.loads refuses trailing text, so the generator does too."""
    text = PACKAGED.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        render(text + " x")
    assert render(text + "\n") == render(text)


def test_the_fixture_holds_nine_cases() -> None:
    """The recorded cases are the nine bad manifests, none of which the old module served."""
    assert len(CASES) == len(set(CASES))
    assert {c["outcome"] for c in CASES.values()} <= {
        "raises KeyError",
        "raises TypeError",
        "raises AttributeError",
        "raises JSONDecodeError",
    }
