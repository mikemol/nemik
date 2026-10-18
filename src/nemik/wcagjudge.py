# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W646: judge the view's colour contrast with the Rego policy in data/wcag.rego.

The facts (nemik.wcagfacts.facts) are measured in Python, the policy decides in Rego, and the pinned
opa runs it through nemik.witnesses.opa_json. A violation is a token pair under its WCAG bar in a
theme; a pair whose token the page does not define is reported as unjudged, never skipped.
"""

from importlib.resources import files

from nemik.wcagfacts import facts
from nemik.witnesses import opa_json

QUERY = '{"violations": data.wcag.violations, "unjudged": data.wcag.unjudged}'
Row = dict[str, object]


def _rows(value: object, key: str) -> list[Row]:
    """Read one list of objects out of the policy's answer.

    Args:
        value: The query's value.
        key: Which list: "violations" or "unjudged".

    Returns:
        The objects under the key; empty when the answer has none.

    """
    found: object = value.get(key) if isinstance(value, dict) else None
    if not isinstance(found, list):
        return []
    return [{str(k): v for k, v in r.items()} for r in found if isinstance(r, dict)]


def _value(answer: object) -> object:
    """Pick the query's value out of opa's JSON answer.

    Args:
        answer: What opa_json returned.

    Returns:
        The first expression's value, or None when there is none.

    """
    result: object = answer.get("result") if isinstance(answer, dict) else None
    first: object = result[0] if isinstance(result, list) and result else None
    exprs: object = first.get("expressions") if isinstance(first, dict) else None
    head: object = exprs[0] if isinstance(exprs, list) and exprs else None
    return head.get("value") if isinstance(head, dict) else None


def judge(html: str) -> dict[str, list[Row]]:
    """Judge a page's contrast in both themes.

    Args:
        html: The page's text.

    Returns:
        {"violations": [...], "unjudged": [...]}: each violation names the criterion, theme, the
        two tokens, the ratio and the bar; each unjudged entry names a theme and a missing token.
        Both are empty when opa is unavailable, which a caller must not read as a pass.

    """
    policy = str(files("nemik").joinpath("data/wcag.rego"))
    value = _value(opa_json(QUERY, facts(html), [policy]))
    return {
        "violations": _rows(value, "violations"),
        "unjudged": _rows(value, "unjudged"),
    }
