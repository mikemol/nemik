# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W646: judge the view's colour contrast with the Rego policy in data/wcag.rego.

The facts (nemik.wcagfacts.facts) are measured in Python, the policy decides in Rego, and the pinned
opa runs it through nemik.witnesses.opa_json. A violation is a token pair under its WCAG bar in a
theme; a pair whose token the page does not define is reported as unjudged, never skipped.
"""

from importlib.resources import files

from nemik.wcagfacts import facts, focus, marks
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


def _document(html: str) -> dict[str, object]:
    """Gather the facts the policy judges.

    Args:
        html: The page's text.

    Returns:
        The colour facts by theme, plus "focus" (2.4.7) and "marks" (1.4.1).

    """
    doc: dict[str, object] = dict(facts(html))
    doc["focus"] = focus(html)
    doc["marks"] = marks(html)
    return doc


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
    value = _value(opa_json(QUERY, _document(html), [policy]))
    return {
        "violations": _rows(value, "violations"),
        "unjudged": _rows(value, "unjudged"),
    }


def judge_targets(targets: list[Row]) -> list[Row]:
    """Judge the sizes of a rendered page's pointer targets (WCAG 2.5.8).

    Args:
        targets: One box per target, {"name", "x", "y", "w", "h"} in CSS pixels, as a
            browser measured them (tests/test_wcag_render.py).

    Returns:
        The undersized targets that a 24 px circle centred on them would leave touching another
        target; each names the criterion, the target and its size. Empty when opa is unavailable,
        which a caller must not read as a pass.

    """
    policy = str(files("nemik").joinpath("data/wcag.rego"))
    doc: dict[str, object] = {"targets": targets}
    value = _value(opa_json(TARGET_QUERY, doc, [policy]))
    return _rows(value, "violations")


TARGET_QUERY = '{"violations": data.wcag.target_violations}'
NAME_QUERY = '{"violations": data.wcag.name_violations}'


def judge_names(names: list[Row]) -> list[Row]:
    """Judge the accessible names of a rendered page's controls (WCAG 4.1.2 and 2.5.3).

    Args:
        names: One row per control, {"target", "accessible", "visible"}: the name a browser
            computes for it and the letters and digits it shows, as tests/test_wcag_render.py
            reads them.

    Returns:
        The controls with no name, and those whose name leaves out the text they show; each
        names the criterion and the target. Empty when opa is unavailable, which a caller must
        not read as a pass.

    """
    policy = str(files("nemik").joinpath("data/wcag.rego"))
    doc: dict[str, object] = {"names": names}
    return _rows(_value(opa_json(NAME_QUERY, doc, [policy])), "violations")
