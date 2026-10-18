# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W527: claim witnesses and warrants name each other, both ways.

paperkit's gate proves each tagged claim is cited. It does not prove that a witness
function is used, nor that a `claim:<key>` check names a key that exists (a renamed
witness passes until it is run). The witnesses file is read as text, so nothing here
imports it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITED = re.compile(r"check\s*=\s*\{claim:([A-Za-z0-9_-]+)\}")
DEFINED = re.compile(r"^def (\w+)\(", re.MULTILINE)
TABLE = re.compile(r"^CLAIMS = \{(.*?)^\}", re.MULTILINE | re.DOTALL)
ENTRY = re.compile(r'"([A-Za-z0-9_-]+)":\s*(\w+),')
NOT_WITNESSES = {"main"}
LEAST_WITNESSES = 19


def _claims_text() -> str:
    """Read the witnesses file.

    Returns:
        The text of checks/claims.py.

    """
    return (ROOT / "checks" / "claims.py").read_text()


def _registered() -> dict[str, str]:
    """Read the CLAIMS table.

    Returns:
        key -> the name of the witness function registered under it.

    """
    table = TABLE.search(_claims_text())
    assert table is not None, "checks/claims.py has no CLAIMS table"
    pairs: list[tuple[str, str]] = ENTRY.findall(table.group(1))
    return dict(pairs)


def _defined() -> set[str]:
    """Name the witness functions the file defines.

    Returns:
        Its public module-level functions but main.

    """
    names: list[str] = DEFINED.findall(_claims_text())
    return {n for n in names if not n.startswith("_")} - NOT_WITNESSES


def _cited() -> set[str]:
    """Name the keys the warrants cite.

    Returns:
        The keys of the warrants' `claim:` checks.

    """
    keys: list[str] = CITED.findall((ROOT / "warrants.bib").read_text())
    return set(keys)


def test_the_table_is_read() -> None:
    """The reader finds the table, so the checks below are not vacuous."""
    assert len(_registered()) >= LEAST_WITNESSES


def test_every_warrant_check_names_a_witness_that_exists() -> None:
    """A warrant citing a key the table lacks would only fail when it ran."""
    missing = sorted(_cited() - set(_registered()))
    assert not missing, f"warrants cite claim keys with no witness: {missing}"


def test_every_witness_is_cited_by_a_warrant() -> None:
    """A witness no warrant cites guards no claim."""
    uncited = sorted(set(_registered()) - _cited())
    assert not uncited, f"witnesses no warrant cites: {uncited}"


def test_every_registered_function_is_defined() -> None:
    """A table entry naming an undefined function fails at import, not here."""
    absent = sorted(set(_registered().values()) - _defined())
    assert not absent, f"CLAIMS names functions the file does not define: {absent}"


def test_every_witness_function_is_registered() -> None:
    """A function written for a claim but left out of CLAIMS can never run."""
    left_out = sorted(_defined() - set(_registered().values()))
    assert not left_out, f"witness functions missing from CLAIMS: {left_out}"
