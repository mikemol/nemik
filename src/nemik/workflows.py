# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W320: nemik's workflows as data, for checking against skills/nemik/SKILL.md.

`data/workflows.toml` declares the card lifecycle, the rules the skill teaches and the
cross-workstream workflows. This module only reads parsed tables of it (nemik:W1179: no import,
so the Codon census can compile it; the file and TOML read is in tests/test_workflows.py, the
correspondence check).
"""


def advice_only(transitions: list[dict[str, object]], rules: list[dict[str, object]]) -> list[str]:
    """List what the skill teaches but nothing checks: lifecycle commands and unenforced rules.

    Args:
        transitions: The lifecycle's transition tables.
        rules: The rule tables.

    Returns:
        One entry per unenforced lifecycle command or rule.

    """
    loose = [
        f"{t['from']}->{t['to']} ({t['command']})" for t in transitions if not t["enforced_by"]
    ]
    loose += [f"rule {r['id']}" for r in rules if not r["enforced_by"]]
    return loose
