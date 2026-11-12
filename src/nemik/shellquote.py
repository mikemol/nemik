# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Quote one word for a POSIX shell, without shlex (nemik:W2104, W2125).

shlex is a Codon wall, so the quoting lives here, in one place: nemik.importer quotes the
commands it prints with it and nemik.spawn quotes every argument of a process it starts through
`sh -c`. A word quoted here arrives at the program exactly as written, whatever it holds:
`$(...)`, backticks, `;`, `|`, `>`, a newline, a single quote. tests/test_shellquote.py fuzzes it
against the shell itself.
"""

# The characters a POSIX shell word may hold unquoted, as shlex.quote decides it (ASCII letters
# and digits, underscore, and @ % + = : , . / -). A string, not a frozenset, which Codon does
# not have; each character is tested alone, so membership means the same.
UNQUOTED = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-"
SINGLE_QUOTE = "'"
ESCAPED_QUOTE = "'\"'\"'"


def quote(word: str) -> str:
    """Quote one word for a POSIX shell exactly as shlex.quote does.

    Returns:
        The word itself when every character is safe, '' for the empty word, else the word in
        single quotes with each single quote written as '"'"'.

    """
    if not word:
        return "''"
    if all(c in UNQUOTED for c in word):
        return word
    return SINGLE_QUOTE + word.replace(SINGLE_QUOTE, ESCAPED_QUOTE) + SINGLE_QUOTE
