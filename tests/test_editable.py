import json

import nemik


class _Dist:
    def __init__(self, text):
        self.text = text

    def read_text(self, name):
        assert name == "direct_url.json"
        return self.text


def test_editable_install_is_detected_and_a_package_install_is_not(monkeypatch) -> None:
    for text, want in ((json.dumps({"url": "file:///x", "dir_info": {"editable": True}}), True),
                       (json.dumps({"url": "file:///x", "dir_info": {}}), False),
                       (None, False)):
        monkeypatch.setattr(nemik, "distribution", lambda _n, t=text: _Dist(t))
        assert nemik.editable_install() is want
