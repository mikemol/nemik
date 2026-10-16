# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W568: a dict merge written as a call, because Codon aborts the compiler on `{**a, "k": v}`.

Codon 0.20.3 hits an assertion ("dictionary items are invalid", expr.cpp:238) on a dict display with
a spread. `merged` is the same operation as a function: the base's keys in their order, then the
extra's, an existing key keeping its place and taking the new value, exactly as the display does.
The parameters are plain dicts because Codon has no collections.abc.
"""


def merged[V](base: dict[str, V], extra: dict[str, V]) -> dict[str, V]:
    """Return a new dict holding the base's items updated with the extra's.

    Args:
        base: The items to start from.
        extra: The items to add or override.

    Returns:
        A new dict equal to `{**base, **extra}`.

    """
    out = dict(base)
    out.update(extra)
    return out
