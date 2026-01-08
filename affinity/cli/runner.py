from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from .click_compat import click
from .context import (
    CLIContext,
    build_result,
    error_info_for_exception,
    exit_code_for_exception,
    normalize_exception,
)
from .render import RenderSettings, render_result
from .results import Artifact, CommandContext, CommandResult


@dataclass(frozen=True, slots=True)
class CommandOutput:
    data: Any | None = None
    context: CommandContext | None = None  # Structured command context
    artifacts: list[Artifact] | None = None
    warnings: list[str] | None = None
    pagination: dict[str, Any] | None = None
    resolved: dict[str, Any] | None = None
    columns: list[dict[str, Any]] | None = None
    rate_limit: Any | None = None
    api_called: bool = False
    exit_code: int = 0  # Allow commands to specify non-zero exit codes (e.g., check-key)


def _emit_json(result: CommandResult) -> None:
    payload = result.model_dump(by_alias=True, mode="json")
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("rateLimit") is None:
        meta.pop("rateLimit", None)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _emit_warnings(*, ctx: CLIContext, warnings: list[str]) -> None:
    if ctx.quiet:
        return
    if not warnings:
        return
    stderr = Console(file=sys.stderr, force_terminal=False)
    for w in warnings:
        stderr.print(f"Warning: {w}")


def emit_result(ctx: CLIContext, result: CommandResult) -> None:
    if ctx.output == "json":
        _emit_json(result)
        if ctx.verbosity >= 1 and not ctx.quiet and result.meta.rate_limit is not None:
            stderr = Console(file=sys.stderr, force_terminal=False)
            rl = result.meta.rate_limit
            footer = []
            if (
                rl.api_key_per_minute.remaining is not None
                and rl.api_key_per_minute.limit is not None
            ):
                footer.append(
                    f"user {rl.api_key_per_minute.remaining}/{rl.api_key_per_minute.limit}"
                )
            if rl.org_monthly.remaining is not None and rl.org_monthly.limit is not None:
                footer.append(f"org {rl.org_monthly.remaining}/{rl.org_monthly.limit}")
            if footer:
                stderr.print(f"rate-limit[{rl.source}]: " + " | ".join(footer))
        return

    render_result(
        result,
        settings=RenderSettings(
            output="table",
            quiet=ctx.quiet,
            verbosity=ctx.verbosity,
            pager=ctx.pager,
            all_columns=ctx.all_columns,
            max_columns=ctx.max_columns,
        ),
    )
    _emit_warnings(ctx=ctx, warnings=result.warnings)
    if ctx.verbosity >= 1 and not ctx.quiet and result.meta.rate_limit is not None:
        stderr = Console(file=sys.stderr, force_terminal=False)
        rl = result.meta.rate_limit
        parts: list[str] = []
        if rl.api_key_per_minute.remaining is not None and rl.api_key_per_minute.limit is not None:
            parts.append(f"user {rl.api_key_per_minute.remaining}/{rl.api_key_per_minute.limit}")
        if rl.org_monthly.remaining is not None and rl.org_monthly.limit is not None:
            parts.append(f"org {rl.org_monthly.remaining}/{rl.org_monthly.limit}")
        if parts:
            extra = ""
            if rl.request_id:
                extra = f" requestId={rl.request_id}"
            stderr.print(f"rate-limit[{rl.source}]: " + " | ".join(parts) + extra)


CommandFn = Callable[[CLIContext, list[str]], CommandOutput]


def run_command(ctx: CLIContext, *, command: str, fn: CommandFn) -> None:
    started = time.time()
    warnings: list[str] = []
    try:
        out = fn(ctx, warnings)

        rate_limit = out.rate_limit
        if rate_limit is None and out.api_called and ctx._client is not None:
            rate_limit = ctx._client.rate_limits.snapshot()

        # Use provided context or create minimal one from command name
        cmd_context = out.context or CommandContext(name=command)

        result = build_result(
            ok=True,
            command=cmd_context,
            started_at=started,
            data=out.data,
            artifacts=out.artifacts,
            warnings=(out.warnings or warnings),
            profile=ctx.profile,
            rate_limit=rate_limit,
            pagination=out.pagination,
            resolved=out.resolved,
            columns=out.columns,
        )
        emit_result(ctx, result)
        raise click.exceptions.Exit(out.exit_code)
    except click.exceptions.Exit:
        raise
    except Exception as exc:
        normalized = normalize_exception(exc, verbosity=ctx.verbosity)
        code = exit_code_for_exception(normalized)
        rate_limit = None
        if ctx._client is not None:
            try:
                rate_limit = ctx._client.rate_limits.snapshot()
            except Exception:
                rate_limit = None

        # Create minimal context for error case
        cmd_context = CommandContext(name=command)

        result = build_result(
            ok=False,
            command=cmd_context,
            started_at=started,
            data=None,
            artifacts=None,
            warnings=warnings,
            profile=ctx.profile,
            rate_limit=rate_limit,
            error=error_info_for_exception(normalized, verbosity=ctx.verbosity),
        )
        emit_result(ctx, result)
        raise click.exceptions.Exit(code) from exc
