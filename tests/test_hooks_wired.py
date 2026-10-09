"""Operator 2026-10-04: mtools' two context hooks (inbound-asks, nemik-check) are wired for this repo.

The hooks are nemik's own dependency (the vendored mikemol-hooks wheel, installed in the built
venv), armed in .claude/settings.json on SessionStart and UserPromptSubmit exactly as mtools'
hooks README prescribes. Wiring is only as good as what it runs, so the test also runs each hook.
"""

import json
import subprocess
from pathlib import Path

import installed

ROOT = Path(__file__).parents[1]
HOOKS = ["mikemol-hook-inbound-asks", "mikemol-hook-nemik-check"]
EVENTS = ["SessionStart", "UserPromptSubmit"]


def test_settings_wire_both_hooks_on_both_events() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())["hooks"]
    for event in EVENTS:
        cmds = [
            h["command"]
            for group in settings[event]
            for h in group["hooks"]
            if h["type"] == "command"
        ]
        for hook in HOOKS:
            assert f'"$CLAUDE_PROJECT_DIR/.venv/bin/{hook}"' in cmds, (event, hook)


def test_each_wired_hook_is_installed_in_the_built_venv() -> None:
    for hook in HOOKS:
        assert (installed._bin()[0] / hook).exists(), hook


def test_a_hook_run_with_a_session_start_payload_exits_zero(tmp_path) -> None:
    """Both hooks never refuse: a SessionStart payload for a repo with no queue is silent, exit 0."""
    env = {
        **installed._bin()[1],
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "TMPDIR": str(tmp_path),
    }
    payload = json.dumps(
        {"hook_event_name": "SessionStart", "session_id": "t", "cwd": str(tmp_path)}
    )
    for hook in HOOKS:
        r = subprocess.run(
            installed.script(hook),
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=90,
            check=False,
        )
        assert r.returncode == 0, (hook, r.stderr[-300:])
