"""nemik:W467: every operator-ask category the view receives has a lane label and help text."""

import re
from importlib.resources import files

from nemik.blocks import CATEGORIES

# nemik:W460: errands are never published to the view (serve drops them), so they have no lane.
UNPUBLISHED = {"errand"}


def test_every_category_has_a_label_and_help() -> None:
    # the page as serve reads it, from the installed package (the gate's sandbox has no src/ tree)
    page = files("nemik.web").joinpath("index.html").read_text()
    table = re.search(r"const LANE = \{(.*?)\};", page)
    assert table, "the LANE table is missing"
    help_block = page[page.index("function lane(cat)") :][:2000]
    for cat in set(CATEGORIES) - UNPUBLISHED:
        key = re.compile(rf'(^|[\s{{,])"?{re.escape(cat)}"?\s*:')
        assert key.search(table[1]), f"{cat} has no lane label"
        assert key.search(help_block), f"{cat} has no lane help"
