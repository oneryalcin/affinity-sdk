"""Command decorators for CLI metadata.

These decorators mark commands with metadata used by the JSON help generator
for MCP tools and automation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .click_compat import click

F = TypeVar("F", bound=Callable[..., object])


def destructive(cmd: click.Command) -> click.Command:
    """Mark a command as destructive (data loss possible).

    Destructive commands require explicit confirmation via --yes flag.

    Usage:
        @person_group.command(name="delete")
        @destructive
        @click.argument("person_id", type=int)
        def person_delete(person_id: int) -> None:
            ...
    """
    cmd.destructive = True  # type: ignore[attr-defined]
    return cmd


def category(cat: str) -> Callable[[click.Command], click.Command]:
    """Tag command category ('read', 'write', or 'local').

    Categories:
        - read: Reads from Affinity API (safe, idempotent)
        - write: Modifies Affinity data (requires caution)
        - local: No API interaction (version, config, completion, etc.)

    Usage:
        @category("read")
        @person_group.command(name="get")
        def person_get(...) -> None:
            ...

    Args:
        cat: One of "read", "write", or "local"
    """
    if cat not in ("read", "write", "local"):
        raise ValueError(f"category must be 'read', 'write', or 'local', got {cat!r}")

    def decorator(cmd: click.Command) -> click.Command:
        cmd.category = cat  # type: ignore[attr-defined]
        return cmd

    return decorator
