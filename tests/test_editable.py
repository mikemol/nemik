# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik.adapter.editable_install tells an editable install from a package install."""

import json
from collections.abc import Callable

import pytest

from nemik import adapter


class _Dist:
    def __init__(self, text: str | None) -> None:
        self.text = text

    def read_text(self, name: str) -> str | None:
        assert name == "direct_url.json"
        return self.text


def _dist_of(text: str | None) -> Callable[[str], _Dist]:
    """Stand in for importlib.metadata.distribution.

    Returns:
        A function that gives, for any name, a dist holding `text`.

    """
    return lambda _name: _Dist(text)


def _payload(dir_info: dict[str, object]) -> str:
    """Write a direct_url.json for a file install.

    Returns:
        The JSON text, whose dir_info is `dir_info`.

    """
    body: dict[str, object] = {"url": "file:///x", "dir_info": dir_info}
    return json.dumps(body)


def test_editable_install_is_detected_and_a_package_install_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editable install is detected and a package install is not."""
    for text, want in (
        (_payload({"editable": True}), True),
        (_payload({}), False),
        (None, False),
    ):
        monkeypatch.setattr(adapter, "distribution", _dist_of(text))
        assert adapter.editable_install() is want
