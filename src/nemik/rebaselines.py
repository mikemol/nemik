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
