# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""text: the page's small pure text and colour functions, over plain data (nemik:W829, W812).

The page's JS copies are retired as the module replaces them.
"""


def repo_hue(repo: str) -> int:
    """Give the hue in degrees (0 to 359) a repo's tiles are drawn in (the page's repoHue).

    A rolling hash of the name's characters: h = (h * 31 + code) % 360.

    Returns:
        The hue.

    """
    hue = 0
    for char in repo:
        hue = (hue * 31 + ord(char)) % 360
    return hue
