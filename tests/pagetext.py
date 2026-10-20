# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W802: the page as a reader sees it, index.html and the files it is split into.

nemik:W799 splits web/index.html by concern into a stylesheet and script modules. A test that
matches on the page's text asks for all of it here, so it keeps passing whichever file a rule lives
in as the split goes on.
"""

from importlib.resources import files
from pathlib import Path

from nemik.serve import PAGE_FILES


def page_text() -> str:
    """Join index.html with each of the page's own files that exists, in PAGE_FILES' order.

    Returns:
        The page's text.

    """
    web = Path(str(files("nemik.web")))
    parts = [(web / "index.html").read_text(encoding="utf-8")]
    parts.extend(
        (web / name).read_text(encoding="utf-8")
        for name in PAGE_FILES
        if (web / name).is_file()
    )
    return "\n".join(parts)
