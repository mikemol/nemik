# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W533: one converge loop for the fleet's apply passes, so each writer does not own a copy.

luthen's pod_reaper.converge reruns a set at a fixed cadence until it ends clean or stuck, retries
a hard halt (most clear on their own), and gives up when the same halt repeats with nothing
changed, because rerunning cannot clear that. The bound is a number of passes, never a clock. This
is that loop with the pass, the record and the pause handed in, and every row naming its trigger.
"""

from collections.abc import Callable

Verdict = dict[str, object]

HALT = 1


class World:
    """What the loop touches, handed in so it can be scripted."""

    def __init__(
        self,
        run_pass: Callable[[], tuple[int, Verdict]],
        record: Callable[[Verdict], None],
        pause: Callable[[], None],
        halt_key: Callable[[Verdict], str],
    ) -> None:
        """Hold the four seams.

        Args:
            run_pass: Runs the set once and returns its exit code and verdict.
            record: Receives one row per pass.
            pause: Waits one poll between passes.
            halt_key: Names a verdict's halt, so the same halt can be recognised.

        """
        self.run_pass = run_pass
        self.record = record
        self.pause = pause
        self.halt_key = halt_key


class Policy:
    """How a converge loop decides."""

    def __init__(
        self, done: list[int], max_passes: int, same_halt: int, pauses: int
    ) -> None:
        """Hold the four limits.

        Args:
            done: Exit codes that end the loop and are returned as they are (clean, stuck).
            max_passes: The pass ceiling; the bound is never a clock.
            same_halt: How many identical halts in a row mean rerunning cannot clear it.
            pauses: How many times the pause is called between passes.

        """
        self.done = done
        self.max_passes = max_passes
        self.same_halt = same_halt
        self.pauses = pauses


def converge(world: World, policy: Policy, trigger: str) -> tuple[int, Verdict]:
    """Rerun a pass until it ends in a done code, repeats a halt, or hits the ceiling.

    Args:
        world: The pass, the record, the pause and the halt naming.
        policy: The done codes, the pass ceiling, the repeat limit and the pause count.
        trigger: What started the run (for example "acute" or "chronic"), put on every row.

    Returns:
        (exit code, verdict). A done code returns with the number of passes added; the same halt
        `same_halt` passes in a row, or no convergence within the ceiling, returns HALT with the
        reason under "converge".

    """
    last = ""
    repeats = 0
    for n in range(1, policy.max_passes + 1):
        code, verdict = world.run_pass()
        # The verdict is nested: nemik.runrows reads verdict.state from an object.
        row: Verdict = {"event": "pass", "n": n, "trigger": trigger, "exit": code}
        row["verdict"] = verdict
        world.record(row)
        if code in policy.done:
            done = dict(verdict)
            done["passes"] = n
            return code, done
        key = world.halt_key(verdict)
        repeats = repeats + 1 if key == last else 1
        last = key
        if repeats >= policy.same_halt:
            halted = dict(verdict)
            halted["passes"] = n
            halted["converge"] = (
                f"the same halt {repeats} passes in a row: rerunning cannot clear it"
            )
            return HALT, halted
        for _ in range(policy.pauses):
            world.pause()
    return HALT, {
        "state": "halted",
        "passes": policy.max_passes,
        "converge": "no convergence within the pass ceiling",
    }
