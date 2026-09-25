"""Global Claude Code hook (UserPromptSubmit, Stop, SessionStart): append one raw fact per event.

Records facts only: when, which session, which repo, which event, and who the prompt came from
(operator / peer session / subagent hand-back / background notice). No classification here:
forecast-vs-interrupt is decided downstream by joining with the paths-forward ledger through
mtools, so the hook never needs to understand a ledger schema. Prompt text is never stored.

Spool: $XDG_STATE_HOME/nemik/events.jsonl (default ~/.local/state/...), append-only JSONL.
Always exits 0 and prints nothing: this hook has no deny path and adds no context.
"""
import json
import os
import sys
import time

SOURCES = (
    ("<cross-session-message", "peer"),
    ("<agent-message", "subagent"),
    ("<task-notification", "background"),
    ("[SYSTEM NOTIFICATION", "background"),
)


def prompt_source(prompt: str) -> str:
    head = prompt.lstrip()[:200]
    for prefix, source in SOURCES:
        if prefix in head:
            return source
    return "operator"


def repo_of(cwd: str) -> str | None:
    # Walk up for a .git entry (dir or worktree file). No subprocess, so no wall-clock bound
    # that could misfire on an oversubscribed host.
    path = os.path.abspath(cwd)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return os.path.basename(path)
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def session_scope() -> str | None:
    # luthen's claude_session_scope puts each session in claude-<repo>-p<pid>.scope; the hook
    # inherits that cgroup, so it is the exact join key to per-session CPU/memory/PSI.
    try:
        with open("/proc/self/cgroup", encoding="utf-8") as f:
            for part in f.read().split("/"):
                if part.startswith("claude-") and part.strip().endswith(".scope"):
                    return part.strip()
    except OSError:
        pass
    return None


def main() -> None:
    envelope = json.loads(sys.stdin.read() or "{}")
    cwd = envelope.get("cwd") or os.getcwd()
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": envelope.get("hook_event_name"),
        "session_id": envelope.get("session_id"),
        "scope": session_scope(),
        "cwd": cwd,
        "repo": repo_of(cwd),
    }
    if "prompt" in envelope:
        event["source"] = prompt_source(envelope["prompt"])
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    spool = os.path.join(state, "nemik", "events.jsonl")
    os.makedirs(os.path.dirname(spool), exist_ok=True)
    with open(spool, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a global hook must never break a session
        print(f"nemik hook: {exc}", file=sys.stderr)
    sys.exit(0)
