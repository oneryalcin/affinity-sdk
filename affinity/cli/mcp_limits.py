"""MCP limit enforcement for CLI commands.

When running via MCP gateway, env vars control pagination limits:
- AFFINITY_MCP_MAX_LIMIT: Maximum allowed --max-results/--limit value
- AFFINITY_MCP_DEFAULT_LIMIT: Default when no limit specified
"""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import click

F = TypeVar("F", bound=Callable[..., Any])


def get_mcp_limits() -> tuple[int | None, int | None]:
    """Get MCP limits from environment.

    Returns:
        Tuple of (max_limit, default_limit), or (None, None) if not in MCP context
        or if env vars contain invalid values.
    """
    max_limit_str = os.environ.get("AFFINITY_MCP_MAX_LIMIT")
    default_limit_str = os.environ.get("AFFINITY_MCP_DEFAULT_LIMIT")

    if max_limit_str is None:
        return None, None

    try:
        max_limit = int(max_limit_str)
        default_limit = int(default_limit_str) if default_limit_str else 1000
        return max_limit, default_limit
    except ValueError:
        # Invalid env var values - fall back to no enforcement
        return None, None


def apply_mcp_limits(
    limit_param: str = "max_results",
    all_pages_param: str | None = "all_pages",
) -> Callable[[F], F]:
    """Decorator that enforces MCP limit caps on commands.

    Args:
        limit_param: Name of the limit parameter (e.g., "max_results", "limit")
        all_pages_param: Name of the all-pages flag parameter, or None if command
            doesn't have --all (e.g., interaction ls, field history)

    Usage:
        @apply_mcp_limits()
        def list_export(..., max_results: int | None, all_pages: bool, ...):
            ...

        @apply_mcp_limits(all_pages_param=None)
        def interaction_ls(..., max_results: int | None, ...):
            ...
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            max_limit, default_limit = get_mcp_limits()

            # Not in MCP context - no enforcement
            if max_limit is None:
                return f(*args, **kwargs)

            # Block --all (should already be blocked in bash, but defense in depth)
            if all_pages_param is not None and kwargs.get(all_pages_param):
                raise click.UsageError(
                    f"--all is not allowed via MCP. "
                    f"Use --max-results {max_limit} or cursor pagination."
                )

            # Cap explicit limit if too high
            current_limit = kwargs.get(limit_param)
            if current_limit is not None and current_limit > max_limit:
                click.echo(
                    f"Warning: --max-results capped at {max_limit} (MCP safety limit)",
                    err=True,
                )
                kwargs[limit_param] = max_limit

            # Inject default limit if none specified
            # Note: If all_pages was True, we would have raised an error above
            if current_limit is None:
                kwargs[limit_param] = default_limit

            return f(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
