# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""The guard for annotation-only imports, as a plain constant (nemik:W2125).

ruff at the 3.14 target wants an import used only in annotations behind `if TYPE_CHECKING:`.
`typing.TYPE_CHECKING` is a name the pinned Codon cannot import, so a module that compiles under
Codon imports the guard from here instead: a local module-level `False` that Codon compiles.
ruff-house.toml names this module in `lint.typing-modules`, so ruff reads the guard as typing's,
and mypy treats any name `TYPE_CHECKING` as true by name, so the guarded imports are checked.
"""

TYPE_CHECKING = False
