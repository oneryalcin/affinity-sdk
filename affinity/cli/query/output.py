"""Output formatters for query results.

Formats query results as JSON, JSONL, Markdown, TOON, CSV, or table.
This module is CLI-only and NOT part of the public SDK API.

Supported output formats:
- JSON: Full structure with data, included, pagination, meta
- JSONL: One JSON object per line (data rows only)
- Markdown: GitHub-flavored markdown table (data rows only)
- TOON: Token-Optimized Object Notation (data rows only)
- CSV: Comma-separated values (data rows only)
- Table: Rich terminal tables
"""

from __future__ import annotations

import json
import logging
from typing import Any

from rich.console import Console

from ..formatters import OutputFormat, format_data, format_jsonl
from .models import ExecutionPlan, QueryResult

logger = logging.getLogger(__name__)

# =============================================================================
# JSON Output
# =============================================================================


def format_json(
    result: QueryResult,
    *,
    pretty: bool = False,
    include_meta: bool = False,
) -> str:
    """Format query result as JSON.

    Args:
        result: Query result
        pretty: If True, pretty-print with indentation
        include_meta: If True, include metadata in output

    Returns:
        JSON string
    """
    output: dict[str, Any] = {"data": result.data}

    if result.included:
        output["included"] = result.included

    if include_meta:
        meta: dict[str, Any] = {}
        # Add standardized summary (using camelCase aliases for consistency)
        if result.summary:
            meta["summary"] = result.summary.model_dump(by_alias=True, exclude_none=True)
        # Add additional execution metadata
        if result.meta:
            meta.update(result.meta)
        output["meta"] = meta

    if result.pagination:
        output["pagination"] = result.pagination

    indent = 2 if pretty else None
    return json.dumps(output, indent=indent, default=str)


# =============================================================================
# Table Output (Rich Table)
# =============================================================================

# Columns to exclude from table output by default (following CLI conventions)
# These are complex nested structures that don't display well in tables
# Use --json to see full data including these columns
_EXCLUDED_TABLE_COLUMNS = frozenset(
    {
        "fields",  # Custom field values - use --json or entity get --all-fields
        "interaction_dates",  # Complex nested dates
        "list_entries",  # List entry associations
        "interactions",  # Null unless explicitly loaded
        "company_ids",  # Empty array unless relationships loaded
        "opportunity_ids",  # Empty array unless relationships loaded
        "current_company_ids",  # Empty array unless relationships loaded
    }
)


def format_table(result: QueryResult) -> str:  # pragma: no cover
    """Format query result as a Rich table (matching CLI conventions).

    Args:
        result: Query result

    Returns:
        Rendered table string
    """
    # Use the CLI's standard table rendering
    from ..render import _render_summary_footer, _table_from_rows

    if not result.data:
        return "No results."

    # Filter out excluded columns (following CLI convention - ls commands don't show fields)
    filtered_data = [
        {k: v for k, v in row.items() if k not in _EXCLUDED_TABLE_COLUMNS} for row in result.data
    ]

    # Build Rich table using CLI's standard function
    table, omitted = _table_from_rows(filtered_data)

    # Render to string
    console = Console(force_terminal=False, width=None)
    with console.capture() as capture:
        console.print(table)

    output = capture.get()

    # Add standardized summary footer
    footer_parts: list[str] = []
    if result.summary:
        footer = _render_summary_footer(result.summary)
        if footer:
            footer_parts.append(footer.plain)

    # Column omission notice
    if omitted > 0:
        footer_parts.append(f"({omitted} columns hidden — use --json for full data)")

    return output + "\n".join(footer_parts)


# =============================================================================
# Dry-Run Output
# =============================================================================


def format_dry_run(plan: ExecutionPlan, *, verbose: bool = False) -> str:  # pragma: no cover
    """Format execution plan for dry-run output.

    Args:
        plan: Execution plan
        verbose: If True, show detailed API call breakdown

    Returns:
        Formatted plan string
    """
    lines: list[str] = []

    lines.append("Query Execution Plan")
    lines.append("=" * 40)
    lines.append("")

    # Query summary
    lines.append("Query:")
    lines.append(f"  $version: {plan.version}")
    lines.append(f"  from: {plan.query.from_}")

    if plan.query.where is not None:
        lines.append("  where: <filter condition>")

    if plan.query.include is not None:
        lines.append(f"  include: {', '.join(plan.query.include)}")

    if plan.query.order_by is not None:
        order_fields = [ob.field or "expr" for ob in plan.query.order_by]
        lines.append(f"  orderBy: {', '.join(order_fields)}")

    if plan.query.limit is not None:
        lines.append(f"  limit: {plan.query.limit}")

    lines.append("")

    # Execution summary
    lines.append("Execution Summary:")
    lines.append(f"  Total steps: {len(plan.steps)}")
    lines.append(f"  Estimated API calls: {plan.total_api_calls}")

    if plan.estimated_records_fetched is not None:
        lines.append(f"  Estimated records: {plan.estimated_records_fetched}")

    if plan.estimated_memory_mb is not None:
        lines.append(f"  Estimated memory: {plan.estimated_memory_mb:.1f} MB")

    lines.append("")

    # Steps
    lines.append("Execution Steps:")
    for step in plan.steps:
        status = "[client]" if step.is_client_side else f"[~{step.estimated_api_calls} calls]"
        lines.append(f"  {step.step_id}. {step.description} {status}")

        if verbose:
            if step.depends_on:
                lines.append(f"      depends on: step {', '.join(map(str, step.depends_on))}")
            if step.filter_pushdown:
                lines.append(f"      pushdown: {step.pushdown_filter}")
            for warning in step.warnings:
                lines.append(f"      [!] {warning}")

    lines.append("")

    # Warnings
    if plan.warnings:
        lines.append("Warnings:")
        for warning in plan.warnings:
            lines.append(f"  [!] {warning}")
        lines.append("")

    # Recommendations
    if plan.recommendations:
        lines.append("Recommendations:")
        for rec in plan.recommendations:
            lines.append(f"  - {rec}")
        lines.append("")

    # Assumptions (always show in verbose, or when includes present)
    has_includes = plan.query.include is not None and len(plan.query.include) > 0
    if verbose or has_includes:
        lines.append("Assumptions:")
        if plan.query.limit is not None:
            lines.append(f"  - Record count: {plan.query.limit} (from limit)")
        else:
            lines.append(f"  - Record count: {plan.estimated_records_fetched} (heuristic estimate)")
        if plan.query.where is not None:
            lines.append("  - Filter selectivity: 50% (heuristic)")
        if has_includes:
            lines.append("  - Include calls: 1 API call per parent record (N+1)")
        lines.append("  - Actual counts may vary; use --dry-run to preview before execution")
        lines.append("")

    return "\n".join(lines)


def format_dry_run_json(plan: ExecutionPlan) -> str:
    """Format execution plan as JSON for MCP.

    Args:
        plan: Execution plan

    Returns:
        JSON string
    """
    # Build execution section with optional note for unbounded queries
    execution: dict[str, Any] = {
        "totalSteps": len(plan.steps),
        "estimatedApiCalls": plan.total_api_calls,
        "estimatedRecords": plan.estimated_records_fetched,
        "estimatedMemoryMb": plan.estimated_memory_mb,
        "requiresExplicitMaxRecords": plan.requires_explicit_max_records,
    }

    # Add explanatory note for unbounded queries
    if plan.total_api_calls == "UNBOUNDED":
        execution["estimatedApiCallsNote"] = "Could be 10K-100K+ based on database size"

    output = {
        "version": plan.version,
        "query": {
            "from": plan.query.from_,
            "where": plan.query.where.model_dump() if plan.query.where else None,
            "include": plan.query.include,
            "orderBy": [ob.model_dump() for ob in plan.query.order_by]
            if plan.query.order_by
            else None,
            "limit": plan.query.limit,
        },
        "execution": execution,
        "steps": [
            {
                "stepId": step.step_id,
                "operation": step.operation,
                "description": step.description,
                "estimatedApiCalls": step.estimated_api_calls,
                "isClientSide": step.is_client_side,
                "dependsOn": step.depends_on,
                "warnings": step.warnings,
            }
            for step in plan.steps
        ],
        "warnings": plan.warnings,
        "recommendations": plan.recommendations,
        "hasExpensiveOperations": plan.has_expensive_operations,
        "requiresFullScan": plan.requires_full_scan,
    }

    return json.dumps(output, indent=2, default=str)


# =============================================================================
# Unified Format Output
# =============================================================================


def format_query_result(
    result: QueryResult,
    format: OutputFormat,
    *,
    pretty: bool = False,
    include_meta: bool = False,
) -> str:
    """Format query result with full structure support.

    For formats that only support flat data (markdown, toon, csv),
    the included/pagination/meta are omitted with a warning.

    Args:
        result: Query result to format
        format: Output format (json, jsonl, markdown, toon, csv)
        pretty: Pretty-print JSON output
        include_meta: Include metadata in JSON output

    Returns:
        Formatted string
    """
    if format == "json":
        # Full structure
        return format_json(result, pretty=pretty, include_meta=include_meta)

    if format == "jsonl":
        # Data rows only, one per line
        return format_jsonl(result.data or [])

    if format in ("markdown", "toon", "csv"):
        # Data only - warn if losing information
        if result.included:
            logger.warning(
                "Included data omitted in %s output (use --output json to see included entities)",
                format,
            )
        fieldnames = list(result.data[0].keys()) if result.data else []
        return format_data(result.data or [], format, fieldnames=fieldnames)

    if format == "table":
        return format_table(result)

    raise ValueError(f"Unknown format: {format}")
