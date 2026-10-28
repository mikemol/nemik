# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1176: a queue's waypoint as typed accessors over the flat tree, not a dict of Any.

The shape is declared once, in src/nemik/data/waypoint.schema.json. `Waypoint` is the interface
consumers type against; `TreeWaypoint` reads it from nemik.tracker's Tree, so no `json.loads` value
of type Any reaches a caller. `Waypoint` is a plain class whose methods raise NotImplementedError,
not an abc.ABC: the pinned Codon has neither `abc` nor `typing.Protocol`, and every module of
src/nemik is compiled by the Codon census. tests/test_waypoint.py holds the real abc check.
A member that is absent or null reads as "" (or 0), the tree's own convention.
"""

from nemik.tracker import INT, LIST, STR, Tree, parse_tree

# the schema's core keys, in the order the accessors are declared; a test holds them to the schema
FIELDS = ("symbol", "title", "status", "enables", "blocked_on", "blocked_kind")


class Waypoint:
    """What a consumer may ask of a waypoint."""

    def symbol(self) -> str:
        """Name the card's symbol, `W` and its number."""
        raise NotImplementedError

    def title(self) -> str:
        """Name the card's one-line title."""
        raise NotImplementedError

    def status(self) -> str:
        """Name the card's status: ready, blocked, working, landed or done."""
        raise NotImplementedError

    def enables(self) -> list[str]:
        """List the symbols this card enables."""
        raise NotImplementedError

    def blocked_on(self) -> list[str]:
        """List what this card waits on."""
        raise NotImplementedError

    def blocked_kind(self) -> str:
        """Name who a block waits on, agent or human; empty when the card is not blocked."""
        raise NotImplementedError

    def ticks_blocked(self) -> int:
        """Count the loop ticks the card has waited blocked; 0 when it carries none."""
        raise NotImplementedError


class TreeWaypoint(Waypoint):
    """A waypoint read from a parsed tree, by the handle of its object."""

    def __init__(self, tree: Tree, at: int) -> None:
        """Hold the tree and the handle of one waypoint object."""
        self.tree = tree
        self.at = at

    def _strings(self, key: str) -> list[str]:
        """Read a member that is a list of strings.

        Returns:
            Each string item, in order; none when the member is absent, null or not a list.

        """
        member = self.tree.get(self.at, key)
        if self.tree.kinds[member] != LIST:
            return []
        return [
            self.tree.texts[i]
            for i in self.tree.kids[member]
            if self.tree.kinds[i] == STR
        ]

    def symbol(self) -> str:
        """Name the card's symbol, `W` and its number.

        Returns:
            The symbol; empty when the card has none.

        """
        return self.tree.string(self.at, "symbol")

    def title(self) -> str:
        """Name the card's one-line title.

        Returns:
            The title; empty when the card has none.

        """
        return self.tree.string(self.at, "title")

    def status(self) -> str:
        """Name the card's status: ready, blocked, working, landed or done.

        Returns:
            The status; empty when the card has none.

        """
        return self.tree.string(self.at, "status")

    def enables(self) -> list[str]:
        """List the symbols this card enables.

        Returns:
            The string items of `enables`, in order.

        """
        return self._strings("enables")

    def blocked_on(self) -> list[str]:
        """List what this card waits on.

        Returns:
            The string items of `blocked_on`, in order.

        """
        return self._strings("blocked_on")

    def blocked_kind(self) -> str:
        """Name who a block waits on, agent or human; empty when the card is not blocked.

        Returns:
            `agent`, `human`, or empty.

        """
        return self.tree.string(self.at, "blocked_kind")

    def ticks_blocked(self) -> int:
        """Count the loop ticks the card has waited blocked; 0 when it carries none.

        Returns:
            The count.

        """
        member = self.tree.get(self.at, "ticks_blocked")
        return self.tree.wholes[member] if self.tree.kinds[member] == INT else 0


def waypoints_of(text: str) -> list[Waypoint]:
    """Read the waypoints of a queue document.

    Args:
        text: The queue file's JSON text.

    Returns:
        One Waypoint per object of its `waypoints` list, in the file's order; none when the
        document has no such list.

    """
    tree = parse_tree(text)
    cards = tree.get(tree.root, "waypoints")
    if tree.kinds[cards] != LIST:
        return []
    return [TreeWaypoint(tree, at) for at in tree.kids[cards]]
