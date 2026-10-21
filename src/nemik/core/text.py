# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""text: the page's small pure text and colour functions, over plain data (nemik:W829, W812).

The page's JS copies are retired as the module replaces them.
"""

import math

# the sRGB curve (WCAG 2): a linear toe below the knee, a power above it
KNEE = 0.03928
TOE = 12.92
OFFSET = 0.055
SCALE = 1.055
GAMMA = 2.4
CHANNEL_MAX = 255.0


def _linear(channel: float) -> float:
    """Undo the sRGB curve on one channel given in 0 to 255.

    Returns:
        The channel as linear light in 0 to 1.

    """
    c = channel / CHANNEL_MAX
    if c <= KNEE:
        return c / TOE
    return math.pow((c + OFFSET) / SCALE, GAMMA)


def luminance(red: float, green: float, blue: float) -> float:
    """Give the WCAG relative luminance of an sRGB colour, each channel in 0 to 255.

    Returns:
        The luminance in 0 (black) to 1 (white).

    """
    return 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)


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
