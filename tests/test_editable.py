# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
import json

import pytest

import nemik


class _Dist:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_text(self, name: str) -> str:
        assert name == "direct_url.json"
        return self.text


def test_editable_install_is_detected_and_a_package_install_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for text, want in (
        (json.dumps({"url": "file:///x", "dir_info": {"editable": True}}), True),
        (json.dumps({"url": "file:///x", "dir_info": {}}), False),
        (None, False),
    ):
        monkeypatch.setattr(nemik, "distribution", lambda _n, t=text: _Dist(t))
        assert nemik.editable_install() is want
