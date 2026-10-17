# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W627: a path counts as edited only with an editing verb before it in its clause."""

from nemik.editverbs import edited_paths


def test_a_path_after_an_editing_verb_is_edited() -> None:
    """Both paths of 'edit a and b' are edited: the verb stands before each in one clause."""
    text = "edit src/nemik/a.py and tests/test_a.py"
    assert edited_paths(text) == ["src/nemik/a.py", "tests/test_a.py"]


def test_a_path_only_read_or_cited_is_not_edited() -> None:
    """Luthen's field result: 'see x' and 'the shape in y' name files without changing them."""
    assert edited_paths("see docs/x.md for the rule") == []
    assert edited_paths("the shape lives in shapes.ttl") == []


def test_the_clause_ends_the_reach_of_a_verb() -> None:
    """A verb in an earlier sentence does not carry to a path in the next one."""
    text = "add the reader. docs/x.md describes the format"
    assert edited_paths(text) == []
    assert edited_paths("see docs/x.md; edit src/nemik/b.py") == ["src/nemik/b.py"]
