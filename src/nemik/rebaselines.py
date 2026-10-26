# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1046: re-baselines, declared, so a change of representation earns no paydown credit.

A ratchet's value falls when debt is paid. It can also fall when what is counted changes: a file
that listed every module and now lists only the failing ones drops by the compiling modules, and no
failing module was fixed. Read as a fall, that would let the pace call a repo ok for many landings
while nothing improved (github-8f, after the operator's ruling that an exemption "just cheats the
ratchet", host 695f3e0a line 97317). So a commit that changes what a ratchet counts declares it
here, with the value before, the value after and the reason, and the pace starts that ratchet's
history at the declared step. Plain strings and integers only, no import, so the Codon census
compiles it.
"""

# (repo, ratchet, value before, value after, reason): reviewed, kept, never deleted, so a later
# series of the same file is a new one
Declared = tuple[str, str, int, int, str]
DECLARED: list[Declared] = [
    (
        "nemik",
        "codon-baseline.json",
        264,
        168,
        (
            "the file lists only the failing modes (W1045): it counted 132 modules x 2 modes, "
            "compiling ones as empty strings, and now counts the 84 failing modules x 2; "
            "no failing module was fixed"
        ),
    ),
    (
        "linux-sources",
        "findings/letter-quotes-baseline.tsv",
        71,
        18,
        (
            "the value is now the sum of the mismatch (2), joined (2) and unjudged (14) columns "
            "(mtools:W1991's value expression); it was the row count with the header and 60 rows "
            "carrying no debt, which could not see a paydown; the freeform column holds quote "
            "lines, not failures, and is excluded; relayed by github-8f from linux-sources:W411, "
            "not read from that repo's file by nemik (W1071)"
        ),
    ),
    (
        "nemik",
        "mypy-baseline.json",
        277,
        5747,
        (
            "the value is now the sum of the counts in the file (ratchets.json, mtools:W1991's "
            "file_rule_count); it was the entry count of the file (144 files and their rules), "
            "which a paydown inside a file that still had findings could not move (github-8f, "
            "2026-10-26: 5758 to 5749 findings read as fell 0); no finding was fixed by the change"
        ),
    ),
    (
        "nemik",
        "ruff-baseline.json",
        1000,
        2686,
        (
            "the value is now the sum of the counts in the file (ratchets.json, mtools:W1991's "
            "file_rule_count); it was the entry count of the file, which a paydown that left a "
            "file with findings could not move; no finding was fixed by the change"
        ),
    ),
]


def since(
    values: list[int], repo: str, ratchet: str, declared: list[Declared]
) -> list[int]:
    """Start a ratchet's history at its latest declared re-baseline.

    Args:
        values: The ratchet's value after each gate run, oldest first.
        repo: The repo.
        ratchet: The ratchet file.
        declared: The declared re-baselines.

    Returns:
        The values from the sample that carries the declared new value right after the declared
        old one, for the latest such step of a declaration for this repo and ratchet; the values
        unchanged when no declaration for it matches a step. An undeclared fall of the same size
        is still a fall.

    """
    start = 0
    for name, file, old, new, _ in declared:
        if name != repo or file != ratchet:
            continue
        for index in range(len(values) - 1, 0, -1):
            if values[index - 1] == old and values[index] == new:
                start = max(start, index)
                break
    return values[start:]
