# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: shellquote.quote is fuzzed against the shell itself, the one quoting both trust.

nemik.importer prints commands quoted with it and nemik.spawn runs every argument through
`sh -c` quoted with it, so a word that did not arrive as written would be a command injection.
Each word of a generated corpus (every pair of a set of troublesome characters, plus long mixed
words) is quoted, handed to a real `sh -c "printf '%s' WORD"` and must come back byte for byte;
and it must equal shlex.quote, whose behaviour it copies, word for word.
"""

import itertools
import shlex

from mikemol.procrun.proc import capture

from nemik.shellquote import quote

TROUBLE = [
    "a",
    " ",
    "'",
    '"',
    "$",
    "`",
    "\\",
    "\n",
    ";",
    "|",
    "&",
    ">",
    "*",
    "!",
    "é",
    "\t",
]
LONG = [
    "$(echo INJECT) `echo BT` ; echo X\nline2 | cat > /dev/null",
    "it's a \"test\" with 'quotes' and \\backslashes\\ and $VAR and ${VAR}",
    "'",
    "''",
    "'\"'\"'",
    "-n",
    "-e",
    "--",
    "a" * 5000,
    "line one\nline two\n\nline four\n",
]
EMPTY = ""


def _words() -> list[str]:
    """Give the generated corpus: the empty word, every pair of trouble characters, long words.

    Returns:
        The words to quote.

    """
    pairs = ["".join(pair) for pair in itertools.product(TROUBLE, repeat=2)]
    return [EMPTY, *TROUBLE, *pairs, *LONG]


def test_a_quoted_word_arrives_at_the_shell_as_written() -> None:
    """Print each corpus word through sh -c printf and get it back exactly."""
    for word in _words():
        done = capture(["sh", "-c", "printf '%s' " + quote(word)])
        assert done.returncode == 0, word
        assert done.stdout == word, word


def test_quote_equals_shlex_quote_word_for_word() -> None:
    """Agree with shlex.quote, which Codon cannot import, on the whole corpus."""
    for word in _words():
        assert quote(word) == shlex.quote(word), word
