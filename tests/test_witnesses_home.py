# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1536: the facts --apply appends as evidence carry no home-directory path."""

from __future__ import annotations

from pathlib import Path

from mikemol.pathsforward.homepath import names_home

from nemik.witnesses import redact_home


def test_a_file_witness_under_the_home_directory_is_redacted_for_the_writer() -> None:
    """The writer refuses a path under the home parent; the redacted facts pass its check."""
    facts = f'{{"file": {{"{Path.home()}/.local/share/x/export.json": {{"exists": true}}}}}}'
    assert names_home(facts)
    assert not names_home(redact_home(facts))
    assert "<home>/" in redact_home(facts)


def test_text_without_a_home_path_is_left_as_it_was() -> None:
    """A witness on a path outside the home directories needs no change."""
    facts = '{"file": {"/var/lib/luthen/textfile/x.prom": {"exists": true}}}'
    assert redact_home(facts) == facts
