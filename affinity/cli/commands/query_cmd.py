"""CLI query command.

Executes structured queries against Affinity data.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, cast

from ..click_compat import RichCommand, click
from ..context import CLIContext
from ..decorators import category, progress_capable
from ..errors import CLIError
from ..options import output_options

# =============================================================================
# CLI Command
# =============================================================================


@category("read")
@progress_capable
@click.command(name="query", cls=RichCommand)
@click.option(
    "--file",
    "-f",
    "file_path",
    type=click.Path(exists=True, path_type=Path),  # type: ignore[type-var]
    help="Read query from JSON file.",
)
@click.option(
    "--query",
    "query_str",
    type=str,
    help="Inline JSON query string.",
)
@click.option(
    "--query-version",
    type=str,
    help="Override $version in query (e.g., '1.0').",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show execution plan without running.",
)
@click.option(
    "--dry-run-verbose",
    is_flag=True,
    help="Show detailed plan with API call breakdown.",
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Require confirmation before expensive operations.",
)
@click.option(
    "--max-records",
    type=int,
    default=10000,
    show_default=True,
    help="Safety limit on total records fetched.",
)
@click.option(
    "--timeout",
    type=float,
    default=300.0,
    show_default=True,
    help="Overall timeout in seconds.",
)
@click.option(
    "--csv",
    "csv_flag",
    is_flag=True,
    help="Output as CSV.",
)
@click.option(
    "--csv-bom",
    is_flag=True,
    help="Add UTF-8 BOM for Excel (use with redirection: --csv --csv-bom > file.csv).",
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Pretty-print JSON output.",
)
@click.option(
    "--include-meta",
    is_flag=True,
    help="Include execution metadata in output.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress progress output.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress.",
)
@output_options
@click.pass_obj
def query_cmd(
    ctx: CLIContext,
    file_path: Path | None,
    query_str: str | None,
    query_version: str | None,
    dry_run: bool,
    dry_run_verbose: bool,
    confirm: bool,
    max_records: int,
    timeout: float,
    csv_flag: bool,
    csv_bom: bool,
    pretty: bool,
    include_meta: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    """Execute a structured query against Affinity data.

    The query can be provided via --file, --query, or piped from stdin.

    \b
    Examples:
      # From file
      xaffinity query --file query.json

      # Inline JSON
      xaffinity query --query '{"from": "persons", "limit": 10}'

      # Dry-run to preview execution plan
      xaffinity query --file query.json --dry-run

      # CSV output
      xaffinity query --file query.json --csv

      # JSON output
      xaffinity query --file query.json --json
    """
    # Detect if --max-records was explicitly provided using Click's ParameterSource
    # (see person_cmds.py:908-914 for similar pattern in the codebase)
    max_records_explicit = False
    click_ctx = click.get_current_context(silent=True)
    if click_ctx is not None:
        get_source = getattr(cast(Any, click_ctx), "get_parameter_source", None)
        if callable(get_source):
            source_enum = getattr(cast(Any, click.core), "ParameterSource", None)
            default_source = getattr(source_enum, "DEFAULT", None) if source_enum else None
            actual_source = get_source("max_records")
            max_records_explicit = actual_source != default_source

    try:
        _query_cmd_impl(
            ctx=ctx,
            file_path=file_path,
            query_str=query_str,
            query_version=query_version,
            dry_run=dry_run,
            dry_run_verbose=dry_run_verbose,
            confirm=confirm,
            max_records=max_records,
            max_records_explicit=max_records_explicit,
            timeout=timeout,
            csv_flag=csv_flag,
            csv_bom=csv_bom,
            pretty=pretty,
            include_meta=include_meta,
            quiet=quiet,
            verbose=verbose,
        )
    except CLIError as e:
        # Display error cleanly without traceback
        click.echo(f"Error: {e.message}", err=True)
        if e.hint:
            click.echo(f"Hint: {e.hint}", err=True)
        raise click.exceptions.Exit(e.exit_code) from None


def _query_cmd_impl(
    *,
    ctx: CLIContext,
    file_path: Path | None,
    query_str: str | None,
    query_version: str | None,
    dry_run: bool,
    dry_run_verbose: bool,
    confirm: bool,
    max_records: int,
    max_records_explicit: bool,
    timeout: float,
    csv_flag: bool,
    csv_bom: bool,
    pretty: bool,
    include_meta: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    """Internal implementation of query command."""
    from affinity.cli.query import (
        QueryExecutionError,
        QueryInterruptedError,
        QueryParseError,
        QuerySafetyLimitError,
        QueryTimeoutError,
        QueryValidationError,
        create_planner,
        parse_query,
    )
    from affinity.cli.query.executor import QueryExecutor
    from affinity.cli.query.output import (
        format_dry_run,
        format_dry_run_json,
        format_json,
        format_table,
    )
    from affinity.cli.query.progress import RichQueryProgress, create_progress_callback

    # Check mutual exclusivity: --csv and --json
    if csv_flag and ctx.output == "json":
        raise CLIError(
            "--csv and --json are mutually exclusive.",
        )

    # Get query input
    query_dict = _get_query_input(file_path, query_str)

    # Parse and validate query
    try:
        parse_result = parse_query(query_dict, version_override=query_version)
    except (QueryParseError, QueryValidationError) as e:
        raise CLIError(f"Query validation failed: {e}") from None

    query = parse_result.query

    # Show parsing warnings
    if parse_result.warnings and not quiet:
        for warning in parse_result.warnings:
            click.echo(f"[warning] {warning}", err=True)

    # Create execution plan
    planner = create_planner(max_records=max_records)
    try:
        plan = planner.plan(query)
    except QueryValidationError as e:
        raise CLIError(f"Query planning failed: {e}") from None

    # Dry-run mode
    if dry_run or dry_run_verbose:
        if ctx.output == "json":
            click.echo(format_dry_run_json(plan))
        else:
            click.echo(format_dry_run(plan, verbose=dry_run_verbose))
        return

    # Check for expensive operations
    if (
        plan.has_expensive_operations
        and confirm
        and not click.confirm(
            f"This query will make approximately {plan.total_api_calls} API calls. Continue?"
        )
    ):
        raise CLIError("Query cancelled by user.")

    # Show warnings
    if plan.warnings and not quiet:
        for warning in plan.warnings:
            click.echo(f"[warning] {warning}", err=True)

    # Resolve client settings before async execution
    warnings_list: list[str] = []
    settings = ctx.resolve_client_settings(warnings=warnings_list)
    for warning in warnings_list:
        click.echo(f"[warning] {warning}", err=True)

    # Execute query
    async def run_query() -> Any:
        from affinity import AsyncAffinity
        from affinity.hooks import ResponseInfo

        from ..query.executor import RateLimitedExecutor

        # Create rate limiter for adaptive throttling
        rate_limiter = RateLimitedExecutor()

        # Combine on_response to feed rate limiter with response data
        original_on_response = settings.on_response

        def combined_on_response(res: ResponseInfo) -> None:
            # Call original callback if it exists
            if original_on_response is not None:
                original_on_response(res)
            # Feed rate limiter with status and remaining quota
            remaining_str = res.headers.get("X-RateLimit-Remaining")
            remaining = int(remaining_str) if remaining_str and remaining_str.isdigit() else None
            rate_limiter.on_response(res.status_code, remaining)

        async with AsyncAffinity(
            api_key=settings.api_key,
            v1_base_url=settings.v1_base_url,
            v2_base_url=settings.v2_base_url,
            timeout=settings.timeout,
            log_requests=settings.log_requests,
            max_retries=settings.max_retries,
            on_request=settings.on_request,
            on_response=combined_on_response,
            on_error=settings.on_error,
            policies=settings.policies,
        ) as client:
            # Create progress callback
            if quiet:
                progress = None
            else:
                progress = create_progress_callback(
                    total_steps=len(plan.steps),
                    quiet=quiet,
                    force_ndjson=ctx.output == "json",
                )

            # Use context manager for Rich progress
            if isinstance(progress, RichQueryProgress):
                with progress:
                    executor = QueryExecutor(
                        client,
                        progress=progress,
                        max_records=max_records,
                        max_records_explicit=max_records_explicit,
                        timeout=timeout,
                        allow_partial=True,
                        rate_limiter=rate_limiter,
                    )
                    result = await executor.execute(plan)
            else:
                executor = QueryExecutor(
                    client,
                    progress=progress,
                    max_records=max_records,
                    max_records_explicit=max_records_explicit,
                    timeout=timeout,
                    allow_partial=True,
                    rate_limiter=rate_limiter,
                )
                result = await executor.execute(plan)

            # Capture rate limit before client closes
            result.rate_limit = client.rate_limits.snapshot()
            return result

    try:
        result = asyncio.run(run_query())
    except QueryValidationError as e:
        # Unbounded quantifier query without explicit --max-records
        raise CLIError(str(e)) from None
    except QueryTimeoutError as e:
        raise CLIError(f"Query timed out after {e.elapsed_seconds:.1f}s: {e}") from None
    except QuerySafetyLimitError as e:
        raise CLIError(f"Query exceeded safety limit: {e}") from None
    except QueryInterruptedError as e:
        if e.partial_results:
            click.echo(
                f"[interrupted] Returning {len(e.partial_results)} partial results",
                err=True,
            )
            from affinity.cli.query.models import QueryResult

            result = QueryResult(data=e.partial_results, meta={"interrupted": True})
        else:
            raise CLIError(f"Query interrupted: {e}") from None
    except QueryExecutionError as e:
        raise CLIError(f"Query execution failed: {e}") from None

    # Format and output results
    if csv_flag:
        from ..csv_utils import write_csv_to_stdout

        if not result.data:
            click.echo("No results.", err=True)
            sys.exit(0)

        # Collect all unique field names from data
        all_keys: set[str] = set()
        for record in result.data:
            all_keys.update(record.keys())
        fieldnames = sorted(all_keys)

        write_csv_to_stdout(rows=result.data, fieldnames=fieldnames, bom=csv_bom)
        sys.exit(0)
    elif ctx.output == "json":
        output = format_json(result, pretty=pretty, include_meta=include_meta)
    elif ctx.output in ("jsonl", "markdown", "toon", "csv"):
        # Use unified formatters for new output formats
        from ..formatters import format_data

        if not result.data:
            click.echo("No results.", err=True)
            sys.exit(0)

        # Collect all unique field names from data
        keys: set[str] = set()
        for record in result.data:
            keys.update(record.keys())
        fieldnames = sorted(keys)

        output = format_data(result.data, ctx.output, fieldnames=fieldnames)
    else:
        # Default to table for interactive use
        output = format_table(result)

    click.echo(output)

    # Show summary if not quiet
    if not quiet and include_meta and result.meta:
        exec_time = result.meta.get("executionTime", 0)
        click.echo(f"\n[info] {len(result.data)} records in {exec_time:.2f}s", err=True)

    # Show rate limit info (at verbose level, matching other commands)
    if verbose and not quiet and result.rate_limit is not None:
        rl = result.rate_limit
        parts: list[str] = []
        if rl.api_key_per_minute.remaining is not None and rl.api_key_per_minute.limit is not None:
            parts.append(f"user {rl.api_key_per_minute.remaining}/{rl.api_key_per_minute.limit}")
        if rl.org_monthly.remaining is not None and rl.org_monthly.limit is not None:
            parts.append(f"org {rl.org_monthly.remaining}/{rl.org_monthly.limit}")
        if parts:
            click.echo(f"rate-limit[{rl.source}]: " + " | ".join(parts), err=True)


def _get_query_input(file_path: Path | None, query_str: str | None) -> dict[str, Any]:
    """Get query input from file, string, or stdin.

    Args:
        file_path: Path to query file
        query_str: Inline JSON string

    Returns:
        Parsed query dict

    Raises:
        CLIError: If no input provided or parsing fails
    """
    if file_path:
        try:
            content = file_path.read_text()
            result: dict[str, Any] = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            raise CLIError(f"Invalid JSON in file: {e}") from None
        except OSError as e:
            raise CLIError(f"Failed to read file: {e}") from None

    if query_str:
        try:
            result = json.loads(query_str)
            return result
        except json.JSONDecodeError as e:
            raise CLIError(f"Invalid JSON: {e}") from None

    # Try stdin
    if not sys.stdin.isatty():
        try:
            content = sys.stdin.read()
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            raise CLIError(f"Invalid JSON from stdin: {e}") from None

    raise CLIError(
        "No query provided. Use --file, --query, or pipe JSON to stdin.\n\n"
        "Examples:\n"
        "  xaffinity query --file query.json\n"
        '  xaffinity query --query \'{"from": "persons", "limit": 10}\'\n'
        '  echo \'{"from": "persons"}\' | xaffinity query'
    )
