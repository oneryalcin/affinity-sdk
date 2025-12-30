from __future__ import annotations

import json
import os
import signal
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal, cast

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from affinity.filters import FilterExpression
from affinity.filters import parse as parse_filter
from affinity.models.entities import FieldMetadata, ListCreate, ListEntryWithEntity
from affinity.models.types import ListType
from affinity.types import (
    AnyFieldId,
    CompanyId,
    EnrichedFieldId,
    FieldId,
    FieldType,
    ListEntryId,
    ListId,
    OpportunityId,
    PersonId,
)

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..csv_utils import artifact_path, write_csv
from ..errors import CLIError
from ..options import output_options
from ..resolve import (
    list_all_saved_views,
    list_fields_for_list,
    resolve_list_selector,
    resolve_saved_view,
)
from ..results import Artifact
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli, serialize_models_for_cli
from ._v1_parsing import parse_json_value


@click.group(name="list", cls=RichGroup)
def list_group() -> None:
    """List commands."""


def _parse_list_type(value: str | None) -> ListType | None:
    if value is None:
        return None
    value = value.lower()
    if value in {"person", "people"}:
        return ListType.PERSON
    if value in {"company", "companies", "organization", "org"}:
        return ListType.ORGANIZATION
    if value in {"opportunity", "opp"}:
        return ListType.OPPORTUNITY
    raise CLIError(f"Unknown list type: {value}", exit_code=2, error_type="usage_error")


@list_group.command(name="ls", cls=RichCommand)
@click.option("--type", "list_type", type=str, default=None, help="Filter by list type.")
@click.option("--page-size", type=int, default=None, help="Page size (limit).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N items total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def list_ls(
    ctx: CLIContext,
    *,
    list_type: str | None,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    List all lists in the workspace.

    Examples:

    - `xaffinitylist ls`
    - `xaffinitylist ls --type person`
    - `xaffinitylist ls --type company --all`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        lt = _parse_list_type(list_type)

        if cursor is not None and page_size is not None:
            raise CLIError(
                "--cursor cannot be combined with --page-size.",
                exit_code=2,
                error_type="usage_error",
            )

        pages = client.lists.pages(limit=page_size, cursor=cursor)
        rows: list[dict[str, object]] = []
        first_page = True

        show_progress = (
            ctx.progress != "never"
            and not ctx.quiet
            and (ctx.progress == "always" or sys.stderr.isatty())
        )

        with ExitStack() as stack:
            progress: Progress | None = None
            task_id: TaskID | None = None
            if show_progress:
                progress = stack.enter_context(
                    Progress(
                        TextColumn("{task.description}"),
                        BarColumn(),
                        TextColumn("{task.completed} rows"),
                        TimeElapsedColumn(),
                        console=Console(file=sys.stderr),
                        transient=True,
                    )
                )
                task_id = progress.add_task("Fetching", total=max_results)

            for page in pages:
                for idx, item in enumerate(page.data):
                    if lt is not None and item.type != lt:
                        continue
                    rows.append(
                        {
                            "id": int(item.id),
                            "name": item.name,
                            "type": ListType(item.type).name.lower(),
                            "ownerId": int(item.owner_id)
                            if getattr(item, "owner_id", None)
                            else None,
                            "isPublic": getattr(item, "is_public", None),
                        }
                    )
                    if progress and task_id is not None:
                        progress.update(task_id, completed=len(rows))
                    if max_results is not None and len(rows) >= max_results:
                        stopped_mid_page = idx < (len(page.data) - 1)
                        if stopped_mid_page:
                            warnings.append(
                                "Results truncated mid-page; resume cursor omitted "
                                "to avoid skipping items. Re-run with a higher "
                                "--max-results or without it to paginate safely."
                            )
                        pagination = None
                        if (
                            page.pagination.next_cursor
                            and not stopped_mid_page
                            and page.pagination.next_cursor != cursor
                        ):
                            pagination = {
                                "lists": {
                                    "nextCursor": page.pagination.next_cursor,
                                    "prevCursor": page.pagination.prev_cursor,
                                }
                            }
                        return CommandOutput(
                            data={"lists": rows[:max_results]},
                            pagination=pagination,
                            api_called=True,
                        )

                if first_page and not all_pages and max_results is None:
                    return CommandOutput(
                        data={"lists": rows},
                        pagination=(
                            {
                                "lists": {
                                    "nextCursor": page.pagination.next_cursor,
                                    "prevCursor": page.pagination.prev_cursor,
                                }
                            }
                            if page.pagination.next_cursor
                            else None
                        ),
                        api_called=True,
                    )
                first_page = False

        return CommandOutput(data={"lists": rows}, pagination=None, api_called=True)

    run_command(ctx, command="list ls", fn=fn)


@list_group.command(name="create", cls=RichCommand)
@click.option("--name", required=True, help="List name.")
@click.option("--type", "list_type", required=True, help="List type (person/company/opportunity).")
@click.option(
    "--public/--private",
    "is_public",
    default=False,
    help="Whether the list is public (default: private).",
)
@click.option("--owner-id", type=int, default=None, help="Owner id.")
@output_options
@click.pass_obj
def list_create(
    ctx: CLIContext,
    *,
    name: str,
    list_type: str,
    is_public: bool,
    owner_id: int | None,
) -> None:
    """
    Create a new list.

    Examples:

    - `xaffinitylist create --name "Prospects" --type company`
    - `xaffinitylist create --name "Candidates" --type person --public`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _ = warnings
        lt = _parse_list_type(list_type)
        if lt is None:
            raise CLIError(
                "Missing list type.",
                exit_code=2,
                error_type="usage_error",
                hint="Use --type person|company|opportunity.",
            )
        client = ctx.get_client(warnings=warnings)
        created = client.lists.create(
            ListCreate(
                name=name,
                type=lt,
                is_public=is_public,
                owner_id=owner_id,
            )
        )
        payload = serialize_model_for_cli(created)
        return CommandOutput(data={"list": payload}, api_called=True)

    run_command(ctx, command="list create", fn=fn)


@list_group.command(name="view", cls=RichCommand)
@click.argument("list_selector")
@output_options
@click.pass_obj
def list_view(ctx: CLIContext, list_selector: str) -> None:
    """
    View list details, fields, and saved views.

    LIST_SELECTOR can be a list id or exact list name.

    Examples:

    - `xaffinitylist view 12345`
    - `xaffinitylist view "Pipeline"`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved = resolve_list_selector(client=client, selector=list_selector)
        list_id = ListId(int(resolved.list.id))
        fields = client.lists.get_fields(list_id)
        views = list_all_saved_views(client=client, list_id=list_id)
        data = {
            "list": serialize_model_for_cli(resolved.list),
            "fields": serialize_models_for_cli(fields),
            "savedViews": serialize_models_for_cli(views),
        }
        return CommandOutput(data=data, resolved=resolved.resolved, api_called=True)

    run_command(ctx, command="list view", fn=fn)


CsvHeaderMode = Literal["names", "ids"]


ExpandChoice = Literal["people", "companies", "opportunities"]
CsvMode = Literal["flat", "nested"]
ExpandOnError = Literal["raise", "skip"]


@list_group.command(name="export", cls=RichCommand)
@click.argument("list_selector")
@click.option("--saved-view", type=str, default=None, help="Saved view id or name.")
@click.option("--field", "fields", type=str, multiple=True, help="Field name or id (repeatable).")
@click.option(
    "--filter",
    "filter_expr",
    type=str,
    default=None,
    help="Filter expression (mutually exclusive with --saved-view).",
)
@click.option(
    "--page-size", type=int, default=100, show_default=True, help="Page size (limit, max 100)."
)
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N rows total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all rows.")
@click.option("--csv", "csv_path", type=click.Path(), default=None, help="Write CSV.")
@click.option(
    "--csv-header",
    type=click.Choice(["names", "ids"]),
    default="names",
    show_default=True,
    help="Use field names or IDs for CSV headers.",
)
@click.option("--csv-bom", is_flag=True, help="Write UTF-8 BOM for Excel.")
@click.option("--dry-run", is_flag=True, help="Validate selectors and print export plan.")
# Expand options (Phase 1)
@click.option(
    "--expand",
    "expand",
    multiple=True,
    type=click.Choice(["people", "companies", "opportunities"]),
    help="Expand associated entities (repeatable). Uses V1 API.",
)
@click.option(
    "--expand-max-results",
    type=int,
    default=100,
    show_default=True,
    help="Max associations per entry per type.",
)
@click.option(
    "--expand-all",
    is_flag=True,
    help="Fetch all associations per entry (no limit).",
)
@click.option(
    "--expand-on-error",
    type=click.Choice(["raise", "skip"]),
    default="raise",
    show_default=True,
    help="How to handle per-entry expansion errors.",
)
@click.option(
    "--csv-mode",
    type=click.Choice(["flat", "nested"]),
    default="flat",
    show_default=True,
    help="CSV expansion format: flat (one row per association) or nested (JSON arrays).",
)
# Phase 4: --expand-fields and --expand-field-type for expanded entity fields
@click.option(
    "--expand-fields",
    "expand_fields",
    multiple=True,
    type=str,
    help="Include specific field by name or ID in expanded entities (repeatable).",
)
@click.option(
    "--expand-field-type",
    "expand_field_types",
    multiple=True,
    type=click.Choice(["global", "enriched", "relationship-intelligence"], case_sensitive=False),
    help="Include all fields of this type in expanded entities (repeatable).",
)
# Phase 5: --expand-filter and --expand-opportunities-list
@click.option(
    "--expand-filter",
    "expand_filter",
    type=str,
    default=None,
    help="Filter expanded entities (e.g., 'field=value' or 'field!=value').",
)
@click.option(
    "--expand-opportunities-list",
    "expand_opps_list",
    type=str,
    default=None,
    help="Scope --expand opportunities to a specific list (id or name).",
)
@output_options
@click.pass_obj
def list_export(
    ctx: CLIContext,
    list_selector: str,
    *,
    saved_view: str | None,
    fields: tuple[str, ...],
    filter_expr: str | None,
    page_size: int,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    csv_path: str | None,
    csv_header: CsvHeaderMode,
    csv_bom: bool,
    dry_run: bool,
    # Expand options
    expand: tuple[str, ...],
    expand_max_results: int,
    expand_all: bool,
    expand_on_error: str,
    csv_mode: str,
    # Phase 4 options
    expand_fields: tuple[str, ...],
    expand_field_types: tuple[str, ...],
    # Phase 5 options
    expand_filter: str | None,
    expand_opps_list: str | None,
) -> None:
    """
    Export list entries to JSON or CSV.

    LIST_SELECTOR can be a list id or exact list name.

    Examples:

    - `xaffinitylist export "Pipeline" --all`
    - `xaffinitylist export 12345 --csv pipeline.csv --all`
    - `xaffinitylist export "Pipeline" --saved-view "Active Deals" --csv deals.csv`
    - `xaffinitylist export "Pipeline" --field Status --field "Deal Size" --all`
    - `xaffinitylist export "Pipeline" --expand people --all --csv opps-with-people.csv`
    - `xaffinitylist export "Pipeline" --expand people --expand companies --all`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        # Parse and validate expand options early
        expand_set = {e.strip().lower() for e in expand if e and e.strip()}
        want_expand = len(expand_set) > 0

        # Validate expand field options require --expand
        if (expand_fields or expand_field_types) and not want_expand:
            raise CLIError(
                "--expand-fields and --expand-field-type require --expand.",
                exit_code=2,
                error_type="usage_error",
                hint="Use --expand people/companies to expand entity associations.",
            )

        # Parse expand field types to FieldType enum
        parsed_expand_field_types: list[FieldType] | None = None
        if expand_field_types:
            parsed_expand_field_types = []
            for ft in expand_field_types:
                ft_lower = ft.strip().lower()
                if ft_lower == "global":
                    parsed_expand_field_types.append(FieldType.GLOBAL)
                elif ft_lower == "enriched":
                    parsed_expand_field_types.append(FieldType.ENRICHED)
                elif ft_lower == "relationship-intelligence":
                    parsed_expand_field_types.append(FieldType.RELATIONSHIP_INTELLIGENCE)

        # Note: expand_fields will be validated and resolved after client is obtained
        # to enable name→ID resolution via API lookup

        # Validate --expand-filter requires --expand (Phase 5)
        if expand_filter and not want_expand:
            raise CLIError(
                "--expand-filter requires --expand.",
                exit_code=2,
                error_type="usage_error",
                hint="Use --expand people/companies/opportunities to expand entity associations.",
            )

        # Validate --expand-opportunities-list requires --expand opportunities (Phase 5)
        if expand_opps_list and "opportunities" not in expand_set:
            raise CLIError(
                "--expand-opportunities-list requires --expand opportunities.",
                exit_code=2,
                error_type="usage_error",
                hint="Use --expand opportunities --expand-opportunities-list <list>.",
            )

        # Parse expand filter expression (Phase 5)
        parsed_expand_filters: FilterExpression | None = None
        if expand_filter:
            try:
                parsed_expand_filters = parse_filter(expand_filter)
            except ValueError as e:
                raise CLIError(
                    f"Invalid expand filter: {e}",
                    exit_code=2,
                    error_type="usage_error",
                    hint=(
                        "Use 'field=value', 'field!=value', 'field=*' (not null), "
                        "or 'field!=*' (is null). "
                        "Combine with '|' (or) and '&' (and)."
                    ),
                ) from e

        if saved_view and filter_expr:
            raise CLIError(
                "--saved-view and --filter are mutually exclusive.",
                exit_code=2,
                error_type="usage_error",
            )
        if cursor and (saved_view or filter_expr or fields):
            raise CLIError(
                "--cursor cannot be combined with --saved-view/--filter/--field.",
                exit_code=2,
                error_type="usage_error",
            )
        if cursor and page_size != 200:
            raise CLIError(
                "--cursor cannot be combined with --page-size (cursor encodes page size).",
                exit_code=2,
                error_type="usage_error",
            )

        if want_expand and cursor:
            raise CLIError(
                "--cursor cannot be combined with --expand.",
                exit_code=2,
                error_type="usage_error",
                hint="For large exports, use streaming CSV output or the SDK with checkpointing.",
            )

        # Warn if both --expand-all and --expand-max-results specified
        if expand_all and expand_max_results != 100:
            warnings.append(
                f"--expand-all specified; ignoring --expand-max-results {expand_max_results}"
            )

        # Determine effective expansion limit
        effective_expand_limit: int | None = None if expand_all else expand_max_results

        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        list_id = ListId(int(resolved_list.list.id))
        # Note: AffinityModel uses use_enum_values=True, so list.type is an int
        list_type_value = resolved_list.list.type
        list_type = (
            ListType(list_type_value) if isinstance(list_type_value, int) else list_type_value
        )
        resolved: dict[str, Any] = dict(resolved_list.resolved)

        # Validate expand options for list type
        if want_expand:
            valid_expand_for_type: dict[ListType, set[str]] = {
                ListType.OPPORTUNITY: {"people", "companies"},
                ListType.PERSON: {"companies", "opportunities"},
                ListType.ORGANIZATION: {"people", "opportunities"},
            }
            valid_for_this_type = valid_expand_for_type.get(list_type, set())
            invalid_expands = expand_set - valid_for_this_type

            if invalid_expands:
                raise CLIError(
                    f"--expand {', '.join(sorted(invalid_expands))} is not valid for "
                    f"{list_type.name.lower()} lists.",
                    exit_code=2,
                    error_type="usage_error",
                    details={"validExpand": sorted(valid_for_this_type)},
                    hint=f"Valid values for {list_type.name.lower()} lists: "
                    f"{', '.join(sorted(valid_for_this_type))}.",
                )

        # Validate and resolve --expand-fields (Phase 4 - Gap 4 fix)
        # Uses API to fetch field metadata and validate field names/IDs
        parsed_expand_fields: list[tuple[str, AnyFieldId]] | None = None
        if expand_fields and want_expand:
            parsed_expand_fields = _validate_and_resolve_expand_fields(
                client=client,
                expand_set=expand_set,
                field_specs=expand_fields,
            )

        # Resolve --expand-opportunities-list if provided (Phase 5)
        resolved_opps_list_id: ListId | None = None
        if expand_opps_list and "opportunities" in expand_set:
            resolved_opps_list = resolve_list_selector(client=client, selector=expand_opps_list)
            # Validate it's an opportunity list
            opps_list_type_value = resolved_opps_list.list.type
            opps_list_type = (
                ListType(opps_list_type_value)
                if isinstance(opps_list_type_value, int)
                else opps_list_type_value
            )
            if opps_list_type != ListType.OPPORTUNITY:
                raise CLIError(
                    f"--expand-opportunities-list must reference an opportunity list, "
                    f"got {opps_list_type.name.lower()} list.",
                    exit_code=2,
                    error_type="usage_error",
                )
            resolved_opps_list_id = ListId(int(resolved_opps_list.list.id))
            resolved["expandOpportunitiesList"] = {
                "listId": int(resolved_opps_list_id),
                "listName": resolved_opps_list.list.name,
            }

        # Warn about expensive --expand opportunities without scoping (Phase 5)
        if "opportunities" in expand_set and resolved_opps_list_id is None:
            warnings.append(
                "Expanding opportunities without --expand-opportunities-list will search "
                "all opportunity lists. This may be slow for large workspaces. "
                "Consider using --expand-opportunities-list to scope the search."
            )

        # Resolve columns/fields.
        field_meta = list_fields_for_list(client=client, list_id=list_id)
        field_by_id: dict[str, FieldMetadata] = {str(f.id): f for f in field_meta}

        selected_field_ids: list[str] = []
        if saved_view:
            view, view_resolved = resolve_saved_view(
                client=client, list_id=list_id, selector=saved_view
            )
            resolved.update(view_resolved)
            selected_field_ids = list(view.field_ids)
            if fields:
                requested_ids = _resolve_field_selectors(fields=fields, field_by_id=field_by_id)
                missing = [fid for fid in requested_ids if fid not in selected_field_ids]
                if missing:
                    message = (
                        "When using --saved-view, --field may only subset/reorder the "
                        "saved view columns."
                    )
                    raise CLIError(
                        message,
                        exit_code=2,
                        error_type="usage_error",
                        details={
                            "missingFieldIds": missing,
                            "savedViewFieldIds": selected_field_ids,
                        },
                    )
                selected_field_ids = requested_ids
        elif fields:
            selected_field_ids = _resolve_field_selectors(fields=fields, field_by_id=field_by_id)
        else:
            selected_field_ids = [str(f.id) for f in field_meta]

        columns = _columns_meta(selected_field_ids, field_by_id=field_by_id)

        if dry_run:
            if want_expand:
                # Cleaner output for --expand mode (omit irrelevant fields like cursor)
                data: dict[str, Any] = {
                    "listId": int(list_id),
                    "listName": resolved_list.list.name,
                    "listType": list_type.name.lower(),
                    "csv": str(csv_path) if csv_path else None,
                }
                if filter_expr:
                    data["filter"] = filter_expr
            else:
                # Standard export - show all query params
                data = {
                    "listId": int(list_id),
                    "listName": resolved_list.list.name,
                    "listType": list_type.name.lower(),
                    "savedView": saved_view,
                    "fieldIds": selected_field_ids,
                    "filter": filter_expr,
                    "pageSize": page_size,
                    "cursor": cursor,
                    "csv": str(csv_path) if csv_path else None,
                }
            if want_expand:
                # Estimate API calls for expansion
                entry_count = resolved_list.list.list_size or 0
                expand_calls = entry_count  # 1 call per entry (optimized for dual)
                data["expand"] = sorted(expand_set)
                data["expandMaxResults"] = effective_expand_limit
                data["csvMode"] = csv_mode if csv_path else None
                # Add dry run warnings
                dry_run_warnings: list[str] = []
                # Handle unreliable listSize from API (often returns 0 for non-empty lists)
                if entry_count == 0:
                    data["estimatedEntries"] = "unknown (API metadata unavailable)"
                    data["estimatedApiCalls"] = "unknown"
                    data["estimatedDuration"] = "unknown"
                    dry_run_warnings.append(
                        "Cannot estimate - Affinity API reports 0 entries but list may "
                        "contain data. The export will fetch all available entries."
                    )
                else:
                    data["estimatedEntries"] = entry_count
                    data["estimatedApiCalls"] = {
                        "listEntries": max(1, entry_count // page_size),
                        "associations": expand_calls,
                        "total": max(1, entry_count // page_size) + expand_calls,
                        "note": (
                            "Using get_associations() optimization "
                            "(both people+companies in 1 call per entry)"
                            if "people" in expand_set and "companies" in expand_set
                            else "1 call per entry"
                        ),
                    }
                    # Estimate duration based on entry count
                    if entry_count <= 50:
                        data["estimatedDuration"] = "~30 seconds to 1 minute"
                    elif entry_count <= 150:
                        data["estimatedDuration"] = f"~2-5 minutes for {entry_count} entries"
                    elif entry_count <= 500:
                        data["estimatedDuration"] = f"~5-10 minutes for {entry_count} entries"
                    else:
                        data["estimatedDuration"] = f"~10-20+ minutes for {entry_count} entries"
                    if entry_count > 1000:
                        dry_run_warnings.append(
                            f"Large export ({entry_count} entries) may take 10-15 minutes or more."
                        )
                dry_run_warnings.append("Expansion uses V1 API which is slower than V2.")
                if effective_expand_limit is not None:
                    dry_run_warnings.append(
                        f"Using --expand-max-results {effective_expand_limit} (default). "
                        "Some entries may have more associations. "
                        "Use --expand-all for complete data."
                    )
                data["warnings"] = dry_run_warnings
            return CommandOutput(
                data=data,
                resolved=resolved,
                columns=columns,
                api_called=True,
            )

        # Build expand field data structures from parsed_expand_fields
        # - expand_field_ids: list of field IDs for API calls
        # - field_id_to_display: dict mapping field ID (str) -> display name (original spec)
        expand_field_ids: list[AnyFieldId] | None = None
        field_id_to_display: dict[str, str] | None = None
        if parsed_expand_fields:
            expand_field_ids = [field_id for _, field_id in parsed_expand_fields]
            field_id_to_display = {
                str(field_id): original for original, field_id in parsed_expand_fields
            }

        # Prepare CSV writing.
        csv_path_obj = Path(csv_path) if csv_path is not None else None
        want_csv = csv_path_obj is not None
        rows_written = 0
        next_cursor: str | None = None

        # Helper to format progress description with association counts
        def _format_progress_desc(
            entries: int,
            total: int | None,
            people_count: int,
            companies_count: int,
            opportunities_count: int,
            expand_set: set[str],
        ) -> str:
            if total and total > 0:
                pct = int(100 * entries / total)
                desc = f"Exporting: {entries}/{total} entries ({pct}%)"
            else:
                desc = f"Exporting: {entries} entries"
            if expand_set:
                parts = []
                if "people" in expand_set and people_count > 0:
                    parts.append(f"{people_count} people")
                if "companies" in expand_set and companies_count > 0:
                    parts.append(f"{companies_count} companies")
                if "opportunities" in expand_set and opportunities_count > 0:
                    parts.append(f"{opportunities_count} opportunities")
                if parts:
                    desc += ", " + " + ".join(parts)
            return desc

        with ExitStack() as stack:
            progress: Progress | None = None
            task_id: TaskID | None = None
            show_progress = (
                ctx.progress != "never"
                and not ctx.quiet
                and (ctx.progress == "always" or sys.stderr.isatty())
            )
            entry_total = resolved_list.list.list_size if want_expand else None
            if show_progress:
                progress = stack.enter_context(
                    Progress(
                        TextColumn("{task.description}"),
                        BarColumn(),
                        TextColumn("{task.completed} rows"),
                        TimeElapsedColumn(),
                        console=Console(file=sys.stderr),
                        transient=True,
                    )
                )
                initial_desc = (
                    "Exporting"
                    if not want_expand
                    else _format_progress_desc(0, entry_total, 0, 0, 0, expand_set)
                )
                task_id = progress.add_task(
                    initial_desc, total=max_results if max_results else None
                )

            if want_csv:
                assert csv_path_obj is not None
                field_headers = [
                    (
                        (field_by_id[fid].name if fid in field_by_id else fid)
                        if csv_header == "names"
                        else fid
                    )
                    for fid in selected_field_ids
                ]
                base_header = [
                    "listEntryId",
                    "entityType",
                    "entityId",
                    "entityName",
                    *field_headers,
                ]

                # Add expansion columns if needed
                if want_expand:
                    header = _expand_csv_headers(
                        base_header,
                        expand_set,
                        csv_mode,
                        expand_fields=parsed_expand_fields,
                        header_mode=csv_header,
                    )
                else:
                    header = base_header

                pid = os.getpid()
                temp_path = csv_path_obj.with_suffix(f"{csv_path_obj.suffix}.{pid}.tmp")
                csv_iter_state: dict[str, Any] = {}
                entries_with_truncated_assoc: list[int] = []
                skipped_entries: list[int] = []
                entries_with_large_nested_assoc: list[int] = []
                csv_associations_fetched: dict[str, int] = {
                    "people": 0,
                    "companies": 0,
                    "opportunities": 0,
                }
                csv_entries_processed = 0

                def iter_rows() -> Any:
                    nonlocal rows_written, next_cursor, csv_entries_processed
                    for row, page_next_cursor in _iterate_list_entries(
                        client=client,
                        list_id=list_id,
                        saved_view=saved_view,
                        filter_expr=filter_expr,
                        selected_field_ids=selected_field_ids,
                        page_size=page_size,
                        cursor=cursor,
                        max_results=max_results,
                        all_pages=all_pages,
                        field_by_id=field_by_id,
                        key_mode=csv_header,
                        state=csv_iter_state,
                    ):
                        next_cursor = page_next_cursor

                        if not want_expand:
                            # No expansion - yield row as-is
                            rows_written += 1
                            if progress is not None and task_id is not None:
                                progress.update(task_id, completed=rows_written)
                            yield row
                            continue

                        # Handle expansion for opportunity lists
                        entity_id = row.get("entityId")
                        if entity_id is None:
                            # No entity - emit row with empty expansion columns
                            expanded_row = dict(row)
                            expanded_row["expandedType"] = ""
                            expanded_row["expandedId"] = ""
                            expanded_row["expandedName"] = ""
                            if "people" in expand_set:
                                expanded_row["expandedEmail"] = ""
                            if "companies" in expand_set:
                                expanded_row["expandedDomain"] = ""
                            rows_written += 1
                            if progress is not None and task_id is not None:
                                progress.update(task_id, completed=rows_written)
                            yield expanded_row
                            continue

                        # Fetch associations based on list type
                        # For flat CSV mode, use prefixed field keys (person.X, company.X)
                        # For nested CSV mode, use unprefixed keys in JSON arrays
                        result = _fetch_associations(
                            client=client,
                            list_type=list_type,
                            entity_id=entity_id,
                            expand_set=expand_set,
                            max_results=effective_expand_limit,
                            on_error=expand_on_error,
                            warnings=warnings,
                            expand_field_types=parsed_expand_field_types,
                            expand_field_ids=expand_field_ids,
                            expand_filters=parsed_expand_filters,
                            expand_opps_list_id=resolved_opps_list_id,
                            field_id_to_display=field_id_to_display,
                            prefix_fields=(csv_mode == "flat"),
                        )

                        if result is None:
                            # Error occurred and on_error='skip'
                            skipped_entries.append(entity_id)
                            continue

                        people, companies, opportunities = result
                        csv_entries_processed += 1
                        csv_associations_fetched["people"] += len(people)
                        csv_associations_fetched["companies"] += len(companies)
                        csv_associations_fetched["opportunities"] += len(opportunities)

                        # Update progress description with association counts
                        if progress is not None and task_id is not None:
                            progress.update(
                                task_id,
                                description=_format_progress_desc(
                                    csv_entries_processed,
                                    entry_total,
                                    csv_associations_fetched["people"],
                                    csv_associations_fetched["companies"],
                                    csv_associations_fetched["opportunities"],
                                    expand_set,
                                ),
                            )

                        # Check for truncation
                        if effective_expand_limit is not None and (
                            len(people) >= effective_expand_limit
                            or len(companies) >= effective_expand_limit
                            or len(opportunities) >= effective_expand_limit
                        ):
                            entries_with_truncated_assoc.append(entity_id)

                        # Handle CSV mode
                        if csv_mode == "flat":
                            # Flat mode: one row per association
                            emitted_any = False

                            # Emit person rows
                            for person in people:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = "person"
                                expanded_row["expandedId"] = person["id"]
                                expanded_row["expandedName"] = person["name"]
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = person.get("primaryEmail") or ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = ""
                                if "opportunities" in expand_set:
                                    expanded_row["expandedListId"] = ""
                                # Copy prefixed field values (Phase 4)
                                for key, val in person.items():
                                    if key.startswith("person."):
                                        expanded_row[key] = val if val is not None else ""
                                rows_written += 1
                                emitted_any = True
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                            # Emit company rows
                            for company in companies:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = "company"
                                expanded_row["expandedId"] = company["id"]
                                expanded_row["expandedName"] = company["name"]
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = company.get("domain") or ""
                                if "opportunities" in expand_set:
                                    expanded_row["expandedListId"] = ""
                                # Copy prefixed field values (Phase 4)
                                for key, val in company.items():
                                    if key.startswith("company."):
                                        expanded_row[key] = val if val is not None else ""
                                rows_written += 1
                                emitted_any = True
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                            # Emit opportunity rows (Phase 5)
                            for opp in opportunities:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = "opportunity"
                                expanded_row["expandedId"] = opp["id"]
                                expanded_row["expandedName"] = opp.get("name") or ""
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = ""
                                if "opportunities" in expand_set:
                                    expanded_row["expandedListId"] = opp.get("listId") or ""
                                rows_written += 1
                                emitted_any = True
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                            # If no associations, emit one row with empty expansion columns
                            if not emitted_any:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = ""
                                expanded_row["expandedId"] = ""
                                expanded_row["expandedName"] = ""
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = ""
                                if "opportunities" in expand_set:
                                    expanded_row["expandedListId"] = ""
                                rows_written += 1
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                        else:
                            # Nested mode: JSON arrays in columns
                            total_assoc = len(people) + len(companies) + len(opportunities)
                            if total_assoc > 100:
                                entries_with_large_nested_assoc.append(entity_id)
                            expanded_row = dict(row)
                            if "people" in expand_set:
                                people_json = json.dumps(people) if people else "[]"
                                expanded_row["_expand_people"] = people_json
                            if "companies" in expand_set:
                                companies_json = json.dumps(companies) if companies else "[]"
                                expanded_row["_expand_companies"] = companies_json
                            if "opportunities" in expand_set:
                                opps_json = json.dumps(opportunities) if opportunities else "[]"
                                expanded_row["_expand_opportunities"] = opps_json
                            rows_written += 1
                            if progress is not None and task_id is not None:
                                progress.update(task_id, completed=rows_written)
                            yield expanded_row

                # Set up interrupt handler to notify user of partial results
                original_handler = signal.getsignal(signal.SIGINT)

                def _interrupt_handler(_signum: int, _frame: Any) -> None:
                    # Re-raise to stop the iteration
                    raise KeyboardInterrupt()

                try:
                    signal.signal(signal.SIGINT, _interrupt_handler)
                    write_result = write_csv(
                        path=temp_path,
                        rows=iter_rows(),
                        fieldnames=header,
                        bom=csv_bom,
                    )
                    temp_path.replace(csv_path_obj)
                except KeyboardInterrupt:
                    # Print interrupt notification with partial file info
                    Console(file=sys.stderr).print(
                        f"\nInterrupted. Partial results in: {temp_path} "
                        f"({rows_written} rows written)"
                    )
                    sys.exit(130)
                finally:
                    signal.signal(signal.SIGINT, original_handler)

                # Add truncation warning if any entries were truncated
                if entries_with_truncated_assoc:
                    count = len(entries_with_truncated_assoc)
                    warnings.append(
                        f"{count} entries had associations truncated at {effective_expand_limit} "
                        "(use --expand-all for complete data)"
                    )

                # Add memory warning for large nested arrays
                if entries_with_large_nested_assoc and csv_mode == "nested":
                    count = len(entries_with_large_nested_assoc)
                    first_id = entries_with_large_nested_assoc[0]
                    warnings.append(
                        f"{count} entries have >100 associations. "
                        f"Large nested arrays may impact memory (e.g., entry {first_id}). "
                        "Consider --csv-mode flat."
                    )

                # Add skipped entries summary with IDs
                if skipped_entries:
                    if len(skipped_entries) <= 10:
                        ids_str = ", ".join(str(eid) for eid in skipped_entries)
                        warnings.append(
                            f"{len(skipped_entries)} entries skipped due to errors: {ids_str} "
                            "(use --expand-on-error raise to fail on errors)"
                        )
                    else:
                        first_ids = ", ".join(str(eid) for eid in skipped_entries[:5])
                        warnings.append(
                            f"{len(skipped_entries)} entries skipped due to errors "
                            f"(first 5: {first_ids}, ...) "
                            "(use --expand-on-error raise to fail on errors)"
                        )

                csv_ref, csv_is_relative = artifact_path(csv_path_obj)
                csv_data: dict[str, Any] = {
                    "listId": int(list_id),
                    "rowsWritten": rows_written,
                    "csv": csv_ref,
                }
                if want_expand:
                    csv_data["entriesProcessed"] = csv_entries_processed + len(skipped_entries)
                    csv_data["associationsFetched"] = {
                        k: v for k, v in csv_associations_fetched.items() if k in expand_set
                    }
                if csv_iter_state.get("truncatedMidPage") is True:
                    warnings.append(
                        "Results truncated mid-page; resume cursor omitted "
                        "to avoid skipping items. Re-run with a higher "
                        "--max-results or without it to paginate safely."
                    )
                return CommandOutput(
                    data=csv_data,
                    artifacts=[
                        Artifact(
                            type="csv",
                            path=csv_ref,
                            path_is_relative=csv_is_relative,
                            rows_written=write_result.rows_written,
                            bytes_written=write_result.bytes_written,
                            partial=False,
                        )
                    ],
                    pagination={"rows": {"nextCursor": next_cursor, "prevCursor": None}}
                    if next_cursor
                    else None,
                    resolved=resolved,
                    columns=columns,
                    api_called=True,
                )

            # JSON/table rows in-memory (small exports).
            # Emit memory warning for large JSON exports with expansion
            if want_expand:
                entry_count = resolved_list.list.list_size or 0
                # Rough estimate: each entry with associations is ~1KB
                estimated_rows = entry_count
                if estimated_rows > 1000:
                    warnings.append(
                        f"JSON output will buffer ~{estimated_rows} rows in memory. "
                        "For large exports, consider --csv for streaming output."
                    )

            rows: list[dict[str, Any]] = []
            table_iter_state: dict[str, Any] = {}
            json_entries_with_truncated_assoc: list[int] = []
            json_skipped_entries: list[int] = []
            associations_fetched: dict[str, int] = {
                "people": 0,
                "companies": 0,
                "opportunities": 0,
            }

            for row, page_next_cursor in _iterate_list_entries(
                client=client,
                list_id=list_id,
                saved_view=saved_view,
                filter_expr=filter_expr,
                selected_field_ids=selected_field_ids,
                page_size=page_size,
                cursor=cursor,
                max_results=max_results,
                all_pages=all_pages,
                field_by_id=field_by_id,
                key_mode="names",
                state=table_iter_state,
            ):
                next_cursor = page_next_cursor

                if not want_expand:
                    rows.append(row)
                    if progress is not None and task_id is not None:
                        progress.update(task_id, completed=len(rows))
                    continue

                # Handle expansion for JSON output (nested arrays)
                entity_id = row.get("entityId")
                if entity_id is None:
                    # No entity - add row with empty arrays
                    expanded_row = dict(row)
                    if "people" in expand_set:
                        expanded_row["people"] = []
                    if "companies" in expand_set:
                        expanded_row["companies"] = []
                    if "opportunities" in expand_set:
                        expanded_row["opportunities"] = []
                    expanded_row["associations"] = "—"
                    rows.append(expanded_row)
                    if progress is not None and task_id is not None:
                        progress.update(task_id, completed=len(rows))
                    continue

                # Fetch associations based on list type
                # For JSON output, use unprefixed field keys in nested arrays
                result = _fetch_associations(
                    client=client,
                    list_type=list_type,
                    entity_id=entity_id,
                    expand_set=expand_set,
                    max_results=effective_expand_limit,
                    on_error=expand_on_error,
                    warnings=warnings,
                    expand_field_types=parsed_expand_field_types,
                    expand_field_ids=expand_field_ids,
                    expand_filters=parsed_expand_filters,
                    expand_opps_list_id=resolved_opps_list_id,
                    field_id_to_display=field_id_to_display,
                    prefix_fields=False,
                )

                if result is None:
                    # Error occurred and on_error='skip' - skip this entry entirely
                    json_skipped_entries.append(entity_id)
                    continue

                people, companies, opportunities = result

                # Check for truncation
                if effective_expand_limit is not None and (
                    len(people) >= effective_expand_limit
                    or len(companies) >= effective_expand_limit
                    or len(opportunities) >= effective_expand_limit
                ):
                    json_entries_with_truncated_assoc.append(entity_id)

                # Track counts
                associations_fetched["people"] += len(people)
                associations_fetched["companies"] += len(companies)
                associations_fetched["opportunities"] += len(opportunities)

                # Update progress description with association counts
                if progress is not None and task_id is not None:
                    progress.update(
                        task_id,
                        description=_format_progress_desc(
                            len(rows) + 1,  # +1 for current entry being processed
                            entry_total,
                            associations_fetched["people"],
                            associations_fetched["companies"],
                            associations_fetched["opportunities"],
                            expand_set,
                        ),
                    )

                # Add nested arrays to row
                expanded_row = dict(row)
                if "people" in expand_set:
                    expanded_row["people"] = people
                if "companies" in expand_set:
                    expanded_row["companies"] = companies
                if "opportunities" in expand_set:
                    expanded_row["opportunities"] = opportunities

                # Add associations summary for table mode
                summary_parts = []
                if "people" in expand_set:
                    pc = len(people)
                    if pc > 0:
                        label = "+ people" if pc >= 100 else " person" if pc == 1 else " people"
                        summary_parts.append(f"{pc}{label}")
                if "companies" in expand_set:
                    cc = len(companies)
                    if cc > 0:
                        if cc >= 100:
                            label = "+ companies"
                        elif cc == 1:
                            label = " company"
                        else:
                            label = " companies"
                        summary_parts.append(f"{cc}{label}")
                if "opportunities" in expand_set:
                    oc = len(opportunities)
                    if oc > 0:
                        if oc >= 100:
                            label = "+ opps"
                        elif oc == 1:
                            label = " opp"
                        else:
                            label = " opps"
                        summary_parts.append(f"{oc}{label}")
                assoc_summary = ", ".join(summary_parts) if summary_parts else "—"
                expanded_row["associations"] = assoc_summary

                rows.append(expanded_row)
                if progress is not None and task_id is not None:
                    progress.update(task_id, completed=len(rows))

            if table_iter_state.get("truncatedMidPage") is True:
                warnings.append(
                    "Results truncated mid-page; resume cursor omitted "
                    "to avoid skipping items. Re-run with a higher "
                    "--max-results or without it to paginate safely."
                )

            # Add truncation warning for JSON output
            if json_entries_with_truncated_assoc:
                count = len(json_entries_with_truncated_assoc)
                warnings.append(
                    f"{count} entries had associations truncated at {effective_expand_limit} "
                    "(use --expand-all for complete data)"
                )

            # Add skipped entries summary for JSON output with IDs
            if json_skipped_entries:
                if len(json_skipped_entries) <= 10:
                    ids_str = ", ".join(str(eid) for eid in json_skipped_entries)
                    warnings.append(
                        f"{len(json_skipped_entries)} entries skipped due to errors: {ids_str} "
                        "(use --expand-on-error raise to fail on errors)"
                    )
                else:
                    first_ids = ", ".join(str(eid) for eid in json_skipped_entries[:5])
                    warnings.append(
                        f"{len(json_skipped_entries)} entries skipped due to errors "
                        f"(first 5: {first_ids}, ...) "
                        "(use --expand-on-error raise to fail on errors)"
                    )

            # Build output data
            output_data: dict[str, Any] = {"rows": rows}
            if want_expand:
                output_data["entriesProcessed"] = len(rows) + len(json_skipped_entries)
                output_data["associationsFetched"] = {
                    k: v for k, v in associations_fetched.items() if k in expand_set
                }

            return CommandOutput(
                data=output_data,
                pagination={"rows": {"nextCursor": next_cursor, "prevCursor": None}}
                if next_cursor
                else None,
                resolved=resolved,
                columns=columns,
                api_called=True,
            )
        raise AssertionError("unreachable")

    run_command(ctx, command="list export", fn=fn)


def _resolve_field_selectors(
    *,
    fields: tuple[str, ...],
    field_by_id: dict[str, FieldMetadata],
) -> list[str]:
    resolved: list[str] = []
    # Build name index for list-scoped fields
    by_name: dict[str, list[str]] = {}
    for fid, meta in field_by_id.items():
        by_name.setdefault(meta.name.lower(), []).append(fid)

    for raw in fields:
        raw = raw.strip()
        if not raw:
            continue
        if raw.isdigit():
            resolved.append(raw)
            continue
        # treat as ID if exact key exists
        if raw in field_by_id:
            resolved.append(raw)
            continue
        matches = by_name.get(raw.lower(), [])
        if not matches:
            raise CLIError(f'Unknown field: "{raw}"', exit_code=2, error_type="usage_error")
        if len(matches) > 1:
            raise CLIError(
                f'Ambiguous field name: "{raw}"',
                exit_code=2,
                error_type="ambiguous_resolution",
                details={"name": raw, "fieldIds": matches},
            )
        resolved.append(matches[0])
    return resolved


def _columns_meta(
    field_ids: list[str],
    *,
    field_by_id: dict[str, FieldMetadata],
) -> list[dict[str, Any]]:
    cols: list[dict[str, Any]] = []
    for fid in field_ids:
        meta = field_by_id.get(fid)
        cols.append(
            {
                "fieldId": fid,
                "fieldName": meta.name if meta else fid,
                "fieldType": meta.type if meta else None,
                "valueType": meta.value_type if meta else None,
            }
        )
    return cols


def _iterate_list_entries(
    *,
    client: Any,
    list_id: ListId,
    saved_view: str | None,
    filter_expr: str | None,
    selected_field_ids: list[str],
    page_size: int,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    field_by_id: dict[str, FieldMetadata],
    key_mode: Literal["names", "ids"],
    state: dict[str, Any] | None = None,
) -> Any:
    """
    Yield `(row_dict, next_cursor)` where `next_cursor` resumes at the next page (not per-row).
    """
    fetched = 0

    entries = client.lists.entries(list_id)

    if saved_view:
        next_page_cursor: str | None = None
        if cursor:
            page = entries.list(cursor=cursor)
        else:
            view, _ = resolve_saved_view(client=client, list_id=list_id, selector=saved_view)
            page = entries.from_saved_view(view.id, limit=page_size)

        next_page_cursor = page.pagination.next_cursor
        for idx, entry in enumerate(page.data):
            fetched += 1
            yield (
                _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                None
                if max_results is not None and fetched >= max_results and idx < (len(page.data) - 1)
                else next_page_cursor,
            )
            if max_results is not None and fetched >= max_results:
                if idx < (len(page.data) - 1) and state is not None:
                    state["truncatedMidPage"] = True
                return

        if not all_pages and max_results is None:
            return

        while next_page_cursor:
            page = entries.list(cursor=next_page_cursor)
            next_page_cursor = page.pagination.next_cursor
            for idx, entry in enumerate(page.data):
                fetched += 1
                yield (
                    _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                    None
                    if max_results is not None
                    and fetched >= max_results
                    and idx < (len(page.data) - 1)
                    else next_page_cursor,
                )
                if max_results is not None and fetched >= max_results:
                    if idx < (len(page.data) - 1) and state is not None:
                        state["truncatedMidPage"] = True
                    return
        return

    pages = (
        entries.pages(cursor=cursor)
        if cursor is not None
        else entries.pages(
            field_ids=selected_field_ids,
            filter=filter_expr,
            limit=page_size,
        )
    )

    first_page = True
    for page in pages:
        next_page_cursor = page.pagination.next_cursor
        for idx, entry in enumerate(page.data):
            fetched += 1
            yield (
                _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                None
                if max_results is not None and fetched >= max_results and idx < (len(page.data) - 1)
                else next_page_cursor,
            )
            if max_results is not None and fetched >= max_results:
                if idx < (len(page.data) - 1) and state is not None:
                    state["truncatedMidPage"] = True
                return

        if first_page and not all_pages and max_results is None:
            return
        first_page = False


def _extract_field_values(obj: Any) -> dict[str, Any]:
    """Extract field values from an object with fields_raw (V2 API) or fields.data (fallback).

    The V2 API returns fields as an array: [{"id": "field-X", "value": {"data": ...}}, ...]
    This helper parses that format into a dict mapping field_id -> value.

    Args:
        obj: An object with `fields_raw` (list) and/or `fields.data` (dict) attributes

    Returns:
        Dict mapping field_id (str) -> field value
    """
    field_values: dict[str, Any] = {}
    fields_raw = getattr(obj, "fields_raw", None)
    if isinstance(fields_raw, list):
        for field_obj in fields_raw:
            if isinstance(field_obj, dict) and "id" in field_obj:
                fid_key = str(field_obj["id"])
                value_wrapper = field_obj.get("value")
                if isinstance(value_wrapper, dict):
                    field_values[fid_key] = value_wrapper.get("data")
                else:
                    field_values[fid_key] = value_wrapper
    else:
        # Fallback to fields.data for older API formats
        fields_attr = getattr(obj, "fields", None)
        if fields_attr is not None and hasattr(fields_attr, "data") and fields_attr.data:
            field_values = dict(fields_attr.data)
    return field_values


def _entry_to_row(
    entry: ListEntryWithEntity,
    field_ids: list[str],
    field_by_id: dict[str, FieldMetadata],
    *,
    key_mode: Literal["names", "ids"],
) -> dict[str, Any]:
    entity_id: int | None = None
    entity_name: str | None = None
    if entry.entity is not None:
        entity_id = int(entry.entity.id)
        entity_name = getattr(entry.entity, "name", None)
        if entity_name is None and hasattr(entry.entity, "full_name"):
            entity_name = cast(Any, entry.entity).full_name
    row: dict[str, Any] = {
        "listEntryId": int(entry.id),
        "entityType": entry.type,
        "entityId": entity_id,
        "entityName": entity_name,
    }

    # Extract field values from entity (V2 API stores fields on entity, not entry)
    field_values = _extract_field_values(entry.entity) if entry.entity else {}

    for fid in field_ids:
        key = fid if key_mode == "ids" else field_by_id[fid].name if fid in field_by_id else fid
        row[key] = field_values.get(str(fid))
    return row


def _person_to_expand_dict(
    person: Any,
    field_types: list[FieldType] | None = None,
    field_ids: list[AnyFieldId] | None = None,
    field_id_to_display: dict[str, str] | None = None,
    prefix_fields: bool = True,
) -> dict[str, Any]:
    """Convert a Person object to an expand dict, including field values if present.

    Args:
        field_id_to_display: Mapping from field ID to display name for --expand-fields
        prefix_fields: If True, prefix field keys with "person." (for flat CSV mode).
                      If False, use unprefixed display names (for nested JSON mode).
    """
    result: dict[str, Any] = {
        "id": int(person.id),
        "name": person.full_name,
        "primaryEmail": person.primary_email or (person.emails[0] if person.emails else None),
    }
    # Include field values if requested and present
    if (field_types or field_ids) and hasattr(person, "fields") and person.fields.requested:
        field_values = _extract_field_values(person)
        for field_id, value in field_values.items():
            # Get display name from mapping, fallback to field_id
            display_name = (
                field_id_to_display.get(str(field_id), str(field_id))
                if field_id_to_display
                else str(field_id)
            )
            if prefix_fields:
                result[f"person.{display_name}"] = value
            else:
                result[display_name] = value
    return result


def _company_to_expand_dict(
    company: Any,
    field_types: list[FieldType] | None = None,
    field_ids: list[AnyFieldId] | None = None,
    field_id_to_display: dict[str, str] | None = None,
    prefix_fields: bool = True,
) -> dict[str, Any]:
    """Convert a Company object to an expand dict, including field values if present.

    Args:
        field_id_to_display: Mapping from field ID to display name for --expand-fields
        prefix_fields: If True, prefix field keys with "company." (for flat CSV mode).
                      If False, use unprefixed display names (for nested JSON mode).
    """
    result: dict[str, Any] = {
        "id": int(company.id),
        "name": company.name,
        "domain": company.domain,
    }
    # Include field values if requested and present
    if (field_types or field_ids) and hasattr(company, "fields") and company.fields.requested:
        field_values = _extract_field_values(company)
        for field_id, value in field_values.items():
            # Get display name from mapping, fallback to field_id
            display_name = (
                field_id_to_display.get(str(field_id), str(field_id))
                if field_id_to_display
                else str(field_id)
            )
            if prefix_fields:
                result[f"company.{display_name}"] = value
            else:
                result[display_name] = value
    return result


def _fetch_opportunity_associations(
    client: Any,
    opportunity_id: OpportunityId,
    *,
    expand_set: set[str],
    max_results: int | None,
    on_error: str,
    warnings: list[str],
    expand_field_types: list[FieldType] | None = None,
    expand_field_ids: list[AnyFieldId] | None = None,
    field_id_to_display: dict[str, str] | None = None,
    prefix_fields: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """
    Fetch people and/or companies associated with an opportunity.

    Returns:
        Tuple of (people_list, companies_list) where each list contains dicts with
        id, name, primaryEmail/domain, plus field values if expand_field_types/ids specified.
        Returns None if error occurred and on_error='skip'.
    """
    want_people = "people" in expand_set
    want_companies = "companies" in expand_set
    want_fields = bool(expand_field_types or expand_field_ids)

    people: list[dict[str, Any]] = []
    companies: list[dict[str, Any]] = []

    try:
        # Use dual optimization if both are requested
        if want_people and want_companies:
            assoc = client.opportunities.get_associations(opportunity_id)
            person_ids = [int(pid) for pid in assoc.person_ids]
            company_ids = [int(cid) for cid in assoc.company_ids]
        else:
            person_ids = []
            company_ids = []
            if want_people:
                person_ids = [
                    int(pid)
                    for pid in client.opportunities.get_associated_person_ids(opportunity_id)
                ]
            if want_companies:
                company_ids = [
                    int(cid)
                    for cid in client.opportunities.get_associated_company_ids(opportunity_id)
                ]

        # Apply max_results limit to IDs before fetching
        if max_results is not None and max_results >= 0:
            person_ids = person_ids[:max_results]
            company_ids = company_ids[:max_results]

        # Fetch people details
        if want_people and person_ids:
            if want_fields:
                # Use V2 API with field types to get field values
                for pid in person_ids:
                    person = client.persons.get(
                        PersonId(pid),
                        field_types=expand_field_types,
                        field_ids=expand_field_ids,
                    )
                    people.append(
                        _person_to_expand_dict(
                            person,
                            expand_field_types,
                            expand_field_ids,
                            field_id_to_display,
                            prefix_fields,
                        )
                    )
            else:
                # Use existing V1 method for core fields only
                fetched_people = client.opportunities.get_associated_people(
                    opportunity_id, max_results=max_results
                )
                people = [_person_to_expand_dict(p) for p in fetched_people]

        # Fetch company details
        if want_companies and company_ids:
            if want_fields:
                # Use V2 API with field types to get field values
                for cid in company_ids:
                    company = client.companies.get(
                        CompanyId(cid),
                        field_types=expand_field_types,
                        field_ids=expand_field_ids,
                    )
                    companies.append(
                        _company_to_expand_dict(
                            company,
                            expand_field_types,
                            expand_field_ids,
                            field_id_to_display,
                            prefix_fields,
                        )
                    )
            else:
                # Use existing V1 method for core fields only
                fetched_companies = client.opportunities.get_associated_companies(
                    opportunity_id, max_results=max_results
                )
                companies = [_company_to_expand_dict(c) for c in fetched_companies]

    except Exception as e:
        if on_error == "skip":
            warnings.append(f"Skipped expansion for opportunity {int(opportunity_id)}: {e}")
            return None
        raise

    return people, companies


def _fetch_company_associations(
    client: Any,
    company_id: CompanyId,
    *,
    expand_set: set[str],
    max_results: int | None,
    on_error: str,
    warnings: list[str],
    expand_field_types: list[FieldType] | None = None,
    expand_field_ids: list[AnyFieldId] | None = None,
    field_id_to_display: dict[str, str] | None = None,
    prefix_fields: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """
    Fetch people associated with a company.

    For company lists, only 'people' expansion is valid.

    Returns:
        Tuple of (people_list, []) where people_list contains dicts with
        id, name, primaryEmail, plus field values if expand_field_types/ids specified.
        Returns None if error occurred and on_error='skip'.
    """
    want_people = "people" in expand_set
    want_fields = bool(expand_field_types or expand_field_ids)

    people: list[dict[str, Any]] = []

    try:
        if want_people:
            # Get person IDs first
            person_ids = client.companies.get_associated_person_ids(
                company_id, max_results=max_results
            )

            if want_fields:
                # Use V2 API with field types to get field values
                for pid in person_ids:
                    person = client.persons.get(
                        pid,
                        field_types=expand_field_types,
                        field_ids=expand_field_ids,
                    )
                    people.append(
                        _person_to_expand_dict(
                            person,
                            expand_field_types,
                            expand_field_ids,
                            field_id_to_display,
                            prefix_fields,
                        )
                    )
            else:
                # Use existing V1 method for core fields only
                fetched_people = client.companies.get_associated_people(
                    company_id, max_results=max_results
                )
                people = [_person_to_expand_dict(p) for p in fetched_people]

    except Exception as e:
        if on_error == "skip":
            warnings.append(f"Skipped expansion for company {int(company_id)}: {e}")
            return None
        raise

    # Return (people, []) - companies is always empty for company list expansion
    return people, []


def _fetch_person_associations(
    client: Any,
    person_id: PersonId,
    *,
    expand_set: set[str],
    max_results: int | None,
    on_error: str,
    warnings: list[str],
    expand_field_types: list[FieldType] | None = None,
    expand_field_ids: list[AnyFieldId] | None = None,
    field_id_to_display: dict[str, str] | None = None,
    prefix_fields: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """
    Fetch companies associated with a person.

    For person lists, only 'companies' expansion is valid.
    Note: V2 API doesn't return company_ids, so we use V1 fallback to get IDs.

    Returns:
        Tuple of ([], companies_list) where companies_list contains dicts with
        id, name, domain, plus field values if expand_field_types/ids specified.
        Returns None if error occurred and on_error='skip'.
    """
    want_companies = "companies" in expand_set
    want_fields = bool(expand_field_types or expand_field_ids)

    companies: list[dict[str, Any]] = []

    try:
        if want_companies:
            # V1 fallback: fetch person via V1 API to get organization_ids
            person_data = client._http.get(f"/persons/{person_id}", v1=True)
            company_ids_raw = (
                person_data.get("organization_ids") or person_data.get("organizationIds") or []
            )
            company_ids = [int(cid) for cid in company_ids_raw if cid is not None]

            # Apply max_results limit
            if max_results is not None and max_results >= 0:
                company_ids = company_ids[:max_results]

            if want_fields:
                # Use V2 API with field types to get field values
                for cid in company_ids:
                    company = client.companies.get(
                        CompanyId(cid),
                        field_types=expand_field_types,
                        field_ids=expand_field_ids,
                    )
                    companies.append(
                        _company_to_expand_dict(
                            company,
                            expand_field_types,
                            expand_field_ids,
                            field_id_to_display,
                            prefix_fields,
                        )
                    )
            else:
                # Fetch company details via V1 API (core fields only)
                for cid in company_ids:
                    company_data = client._http.get(f"/organizations/{cid}", v1=True)
                    companies.append(
                        {
                            "id": cid,
                            "name": company_data.get("name"),
                            "domain": company_data.get("domain"),
                        }
                    )

    except Exception as e:
        if on_error == "skip":
            warnings.append(f"Skipped expansion for person {int(person_id)}: {e}")
            return None
        raise

    # Return ([], companies) - people is always empty for person list expansion
    return [], companies


def _fetch_associations(
    client: Any,
    list_type: ListType,
    entity_id: int,
    *,
    expand_set: set[str],
    max_results: int | None,
    on_error: str,
    warnings: list[str],
    expand_field_types: list[FieldType] | None = None,
    expand_field_ids: list[AnyFieldId] | None = None,
    expand_filters: FilterExpression | None = None,
    expand_opps_list_id: ListId | None = None,
    field_id_to_display: dict[str, str] | None = None,
    prefix_fields: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]] | None:
    """
    Dispatch to the correct association fetcher based on list type.

    Routes to:
    - _fetch_opportunity_associations for opportunity lists
    - _fetch_company_associations for company/organization lists
    - _fetch_person_associations for person lists

    Args:
        field_id_to_display: Mapping from field ID to display name for --expand-fields
        prefix_fields: If True, prefix field keys with entity type (for flat CSV mode).

    Returns:
        Tuple of (people_list, companies_list, opportunities_list).
        Returns None if error occurred and on_error='skip'.
    """
    people: list[dict[str, Any]] = []
    companies: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []

    try:
        if list_type == ListType.OPPORTUNITY:
            result = _fetch_opportunity_associations(
                client=client,
                opportunity_id=OpportunityId(entity_id),
                expand_set=expand_set,
                max_results=max_results,
                on_error=on_error,
                warnings=warnings,
                expand_field_types=expand_field_types,
                expand_field_ids=expand_field_ids,
                field_id_to_display=field_id_to_display,
                prefix_fields=prefix_fields,
            )
            if result is None:
                return None
            people, companies = result

        elif list_type == ListType.ORGANIZATION:
            result = _fetch_company_associations(
                client=client,
                company_id=CompanyId(entity_id),
                expand_set=expand_set,
                max_results=max_results,
                on_error=on_error,
                warnings=warnings,
                expand_field_types=expand_field_types,
                expand_field_ids=expand_field_ids,
                field_id_to_display=field_id_to_display,
                prefix_fields=prefix_fields,
            )
            if result is None:
                return None
            people, _ = result

            # Fetch opportunities if requested (Phase 5)
            if "opportunities" in expand_set:
                opportunities = _fetch_entity_opportunities(
                    client=client,
                    entity_type="company",
                    entity_id=CompanyId(entity_id),
                    opps_list_id=expand_opps_list_id,
                    max_results=max_results,
                    on_error=on_error,
                    warnings=warnings,
                )

        elif list_type == ListType.PERSON:
            result = _fetch_person_associations(
                client=client,
                person_id=PersonId(entity_id),
                expand_set=expand_set,
                max_results=max_results,
                on_error=on_error,
                warnings=warnings,
                expand_field_types=expand_field_types,
                expand_field_ids=expand_field_ids,
                field_id_to_display=field_id_to_display,
                prefix_fields=prefix_fields,
            )
            if result is None:
                return None
            _, companies = result

            # Fetch opportunities if requested (Phase 5)
            if "opportunities" in expand_set:
                opportunities = _fetch_entity_opportunities(
                    client=client,
                    entity_type="person",
                    entity_id=PersonId(entity_id),
                    opps_list_id=expand_opps_list_id,
                    max_results=max_results,
                    on_error=on_error,
                    warnings=warnings,
                )

        else:
            raise ValueError(f"Unsupported list type for expansion: {list_type}")

        # Apply expand filters (Phase 5)
        if expand_filters:
            people = [p for p in people if expand_filters.matches(p)]
            companies = [c for c in companies if expand_filters.matches(c)]
            opportunities = [o for o in opportunities if expand_filters.matches(o)]

        return people, companies, opportunities

    except Exception as e:
        if on_error == "skip":
            warnings.append(f"Skipped expansion for entity {entity_id}: {e}")
            return None
        raise


def _fetch_entity_opportunities(
    client: Any,
    entity_type: str,
    entity_id: PersonId | CompanyId,
    *,
    opps_list_id: ListId | None,
    max_results: int | None,
    on_error: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    """
    Fetch opportunities associated with a person or company.

    If opps_list_id is provided, only search that specific opportunity list.
    Otherwise, search all accessible opportunity lists.

    Returns list of opportunity dicts with id, name, listId.
    """
    opportunities: list[dict[str, Any]] = []

    try:
        # Get opportunity lists to search
        if opps_list_id is not None:
            opp_list_ids = [opps_list_id]
        else:
            # Fetch all opportunity lists the user has access to
            opp_list_ids = []
            for page in client.lists.pages():
                for lst in page.data:
                    if lst.type == ListType.OPPORTUNITY:
                        opp_list_ids.append(ListId(int(lst.id)))

        # Search each opportunity list for entries associated with this entity
        for list_id in opp_list_ids:
            entries = client.lists.entries(list_id)

            # Fetch entries from this list and check associations
            # Note: This is expensive as we need to check each entry's associations
            for page in entries.pages(limit=100):
                for entry in page.data:
                    if entry.entity is None:
                        continue

                    opp_id = OpportunityId(int(entry.entity.id))

                    # Check if this opportunity is associated with our entity
                    try:
                        assoc = client.opportunities.get_associations(opp_id)
                        is_associated = False

                        if entity_type == "person":
                            person_ids = [int(pid) for pid in assoc.person_ids]
                            is_associated = int(entity_id) in person_ids
                        elif entity_type == "company":
                            company_ids = [int(cid) for cid in assoc.company_ids]
                            is_associated = int(entity_id) in company_ids

                        if is_associated:
                            opportunities.append(
                                {
                                    "id": int(opp_id),
                                    "name": getattr(entry.entity, "name", None),
                                    "listId": int(list_id),
                                }
                            )

                            # Apply max results limit
                            if max_results is not None and len(opportunities) >= max_results:
                                return opportunities

                    except Exception:
                        # Skip opportunities we can't access
                        continue

                # Stop pagination if we have enough results
                if max_results is not None and len(opportunities) >= max_results:
                    break

    except Exception as e:
        if on_error == "skip":
            warnings.append(f"Error fetching opportunities for {entity_type} {int(entity_id)}: {e}")
        else:
            raise

    return opportunities


def _validate_and_resolve_expand_fields(
    client: Any,
    expand_set: set[str],
    field_specs: tuple[str, ...],
) -> list[tuple[str, AnyFieldId]]:
    """
    Validate --expand-fields against available global/enriched fields.

    Fetches field metadata for expanded entity types (person/company) and validates
    that each field spec exists. Field specs can be:
    - Field names (resolved to IDs via metadata lookup)
    - Field IDs (validated against metadata)

    Args:
        client: Affinity client instance
        expand_set: Set of expand types ("people", "companies")
        field_specs: Tuple of field spec strings from --expand-fields

    Returns:
        List of (original_spec, resolved_field_id) tuples

    Raises:
        CLIError: If a field spec doesn't match any available field
    """
    # Build combined field lookup from person and company metadata
    # Maps lowercase name -> (display_name, field_id) for name resolution
    # Also stores field_id -> (display_name, field_id) for ID validation
    name_to_field: dict[str, tuple[str, AnyFieldId]] = {}
    id_to_field: dict[str, tuple[str, AnyFieldId]] = {}
    all_field_names: set[str] = set()

    if "people" in expand_set:
        person_fields = client.persons.get_fields()
        for f in person_fields:
            name_lower = f.name.lower()
            name_to_field[name_lower] = (f.name, f.id)
            id_to_field[str(f.id)] = (f.name, f.id)
            all_field_names.add(f.name)

    if "companies" in expand_set:
        company_fields = client.companies.get_fields()
        for f in company_fields:
            name_lower = f.name.lower()
            # Only add if not already present (person fields take precedence)
            if name_lower not in name_to_field:
                name_to_field[name_lower] = (f.name, f.id)
            if str(f.id) not in id_to_field:
                id_to_field[str(f.id)] = (f.name, f.id)
                all_field_names.add(f.name)

    # Resolve each field spec
    parsed: list[tuple[str, AnyFieldId]] = []
    for spec in field_specs:
        spec = spec.strip()
        if not spec:
            continue

        # Try to match by field ID first (exact match)
        if spec in id_to_field:
            display_name, field_id = id_to_field[spec]
            parsed.append((display_name, field_id))
            continue

        # Try to parse as FieldId format (field-123)
        try:
            field_id = FieldId(spec)
            if str(field_id) in id_to_field:
                display_name, _ = id_to_field[str(field_id)]
                parsed.append((display_name, field_id))
                continue
            # Valid FieldId format but not found - try name lookup next
        except ValueError:
            pass

        # Try to match by name (case-insensitive)
        spec_lower = spec.lower()
        if spec_lower in name_to_field:
            display_name, field_id = name_to_field[spec_lower]
            parsed.append((display_name, field_id))
            continue

        # Not found - raise error with helpful message
        # Show a sample of available field names (up to 10)
        sample_names = sorted(all_field_names)[:10]
        hint_suffix = ", ..." if len(all_field_names) > 10 else ""
        raise CLIError(
            f"Unknown expand field: '{spec}'",
            exit_code=2,
            error_type="usage_error",
            details={"availableFields": sorted(all_field_names)[:20]},
            hint=f"Available fields include: {', '.join(sample_names)}{hint_suffix}",
        )

    return parsed


def _expand_csv_headers(
    base_headers: list[str],
    expand_set: set[str],
    csv_mode: str = "flat",
    expand_fields: list[tuple[str, AnyFieldId]] | None = None,
    header_mode: CsvHeaderMode = "names",
) -> list[str]:
    """
    Add expansion columns to CSV headers.

    Flat mode: expandedType, expandedId, expandedName, expandedEmail, expandedDomain,
               plus prefixed field columns (person.{name/id}, company.{name/id}) for --expand-fields
    Nested mode: _expand_people, _expand_companies (JSON arrays)

    Args:
        expand_fields: List of (original_spec, field_id) tuples
        header_mode: "names" uses original spec, "ids" uses field ID
    """
    headers = list(base_headers)
    if csv_mode == "nested":
        # Nested mode: add JSON array columns
        if "people" in expand_set:
            headers.append("_expand_people")
        if "companies" in expand_set:
            headers.append("_expand_companies")
        if "opportunities" in expand_set:
            headers.append("_expand_opportunities")
    else:
        # Flat mode: add row-per-association columns
        headers.append("expandedType")
        headers.append("expandedId")
        headers.append("expandedName")
        if "people" in expand_set:
            headers.append("expandedEmail")
        if "companies" in expand_set:
            headers.append("expandedDomain")
        if "opportunities" in expand_set:
            headers.append("expandedListId")
        # Add prefixed columns for --expand-fields (Phase 4)
        if expand_fields:
            for original_spec, field_id in expand_fields:
                # Use original spec name for "names" mode, field ID for "ids" mode
                display_name = original_spec if header_mode == "names" else str(field_id)
                if "people" in expand_set:
                    headers.append(f"person.{display_name}")
                if "companies" in expand_set:
                    headers.append(f"company.{display_name}")
    return headers


@list_group.group(name="entry", cls=RichGroup)
def list_entry_group() -> None:
    """List entry commands."""


@list_entry_group.command(name="get", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@output_options
@click.pass_obj
def list_entry_get(
    ctx: CLIContext,
    list_selector: str,
    entry_id: int,
) -> None:
    """
    Get a single list entry by ID.

    Displays the list entry with its field values and field names.

    Examples:

    - `xaffinity list entry get "Portfolio" 12345`
    - `xaffinity list entry get 67890 12345`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)
        entry = entries.get(ListEntryId(entry_id))
        payload = serialize_model_for_cli(entry)

        # Include raw fields if available
        fields_raw = getattr(entry, "fields_raw", None)
        if isinstance(fields_raw, list):
            payload["fields"] = fields_raw

        resolved = dict(resolved_list.resolved)

        # Fetch field metadata if fields are present
        entry_fields = payload.get("fields") if isinstance(payload, dict) else None
        if isinstance(entry_fields, list) and entry_fields:
            try:
                from ..field_utils import build_field_id_to_name_map

                field_metadata = client.lists.get_fields(resolved_list.list.id)
                resolved["fieldMetadata"] = build_field_id_to_name_map(field_metadata)
            except Exception:
                # Field metadata is optional - continue without names if fetch fails
                pass

        return CommandOutput(
            data={"listEntry": payload},
            resolved=resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry get", fn=fn)


def _validate_entry_target(
    person_id: int | None,
    company_id: int | None,
) -> None:
    count = sum(1 for value in (person_id, company_id) if value is not None)
    if count == 1:
        return
    raise CLIError(
        "Provide exactly one of --person-id or --company-id.",
        error_type="usage_error",
        exit_code=2,
    )


@list_entry_group.command(name="add", cls=RichCommand)
@click.argument("list_selector")
@click.option("--person-id", type=int, default=None, help="Person id to add.")
@click.option("--company-id", type=int, default=None, help="Company id to add.")
@click.option("--creator-id", type=int, default=None, help="Creator id override.")
@output_options
@click.pass_obj
def list_entry_add(
    ctx: CLIContext,
    list_selector: str,
    *,
    person_id: int | None,
    company_id: int | None,
    creator_id: int | None,
) -> None:
    """Add a person or company to a list (V1 write path).

    Note: Opportunities cannot be added to lists this way. Use 'opportunity create --list-id'
    instead, which creates both the opportunity and its list entry atomically.
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _validate_entry_target(person_id, company_id)
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)

        if person_id is not None:
            created = entries.add_person(PersonId(person_id), creator_id=creator_id)
        else:
            assert company_id is not None
            created = entries.add_company(CompanyId(company_id), creator_id=creator_id)

        payload = serialize_model_for_cli(created)
        return CommandOutput(
            data={"listEntry": payload},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry add", fn=fn)


@list_entry_group.command(name="delete", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@output_options
@click.pass_obj
def list_entry_delete(ctx: CLIContext, list_selector: str, entry_id: int) -> None:
    """Delete a list entry (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)
        success = entries.delete(ListEntryId(entry_id))
        return CommandOutput(
            data={"success": success},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry delete", fn=fn)


@list_entry_group.command(name="set-field", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@click.option("-f", "--field", "field_name", help="Field name (e.g. 'Status').")
@click.option("--field-id", help="Field ID (e.g. 'field-260415').")
@click.option("--value", help="Value to set (string).")
@click.option("--value-json", help="Value to set (JSON).")
@click.option("--append", is_flag=True, help="Append to multi-value field instead of replacing.")
@output_options
@click.pass_obj
def list_entry_set_field(
    ctx: CLIContext,
    list_selector: str,
    entry_id: int,
    *,
    field_name: str | None,
    field_id: str | None,
    value: str | None,
    value_json: str | None,
    append: bool,
) -> None:
    """
    Set a field value on a list entry.

    Use --field for field name resolution or --field-id for direct field ID.
    Use --append for multi-value fields to add without replacing existing values.

    Examples:

    - `xaffinity list entry set-field "Portfolio" 123 --field Status --value "Active"`
    - `xaffinity list entry set-field 67890 123 --field-id field-260415 --value "High"`
    - `xaffinity list entry set-field "Deals" 123 --field Tags --value "Priority" --append`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        from ..field_utils import (
            FieldResolver,
            find_field_values_for_field,
            validate_field_option_mutual_exclusion,
        )

        validate_field_option_mutual_exclusion(field=field_name, field_id=field_id)

        if value is None and value_json is None:
            raise CLIError(
                "Provide --value or --value-json.",
                exit_code=2,
                error_type="usage_error",
            )
        if value is not None and value_json is not None:
            raise CLIError(
                "Use only one of --value or --value-json.",
                exit_code=2,
                error_type="usage_error",
            )

        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        resolved = dict(resolved_list.resolved)

        # Fetch field metadata
        field_metadata = client.lists.get_fields(resolved_list.list.id)
        resolver = FieldResolver(field_metadata)

        target_field_id = (
            field_id
            if field_id
            else resolver.resolve_field_name_or_id(field_name or "", context="field")
        )
        resolved["fieldId"] = target_field_id
        resolved["fieldName"] = resolver.get_field_name(target_field_id)

        # Check if field allows multiple values
        field_allows_multiple = False
        for fm in field_metadata:
            if str(fm.id) == target_field_id:
                field_allows_multiple = fm.allows_multiple
                break

        # If not appending and field has existing values, delete them first
        if not append:
            existing_values = client.field_values.list(list_entry_id=ListEntryId(entry_id))
            existing_for_field = find_field_values_for_field(
                field_values=[serialize_model_for_cli(v) for v in existing_values],
                field_id=target_field_id,
            )
            if existing_for_field:
                if not field_allows_multiple:
                    # Single-value field: delete existing value
                    for fv in existing_for_field:
                        fv_id = fv.get("id")
                        if fv_id:
                            client.field_values.delete(fv_id)
                else:
                    # Multi-value field without --append: error
                    field_label = resolved["fieldName"] or target_field_id
                    raise CLIError(
                        f"Field '{field_label}' has {len(existing_for_field)} value(s). "
                        "Use --append to add, or unset-field first.",
                        exit_code=2,
                        error_type="usage_error",
                    )

        # Set the field value using the V2 API
        entries = client.lists.entries(resolved_list.list.id)
        parsed_value = value if value_json is None else parse_json_value(value_json, label="value")
        try:
            parsed_field_id: AnyFieldId = FieldId(target_field_id)
        except ValueError:
            parsed_field_id = EnrichedFieldId(target_field_id)

        result = entries.update_field_value(ListEntryId(entry_id), parsed_field_id, parsed_value)
        payload = serialize_model_for_cli(result)

        return CommandOutput(
            data={"fieldValue": payload},
            resolved=resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry set-field", fn=fn)


@list_entry_group.command(name="set-fields", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@click.option(
    "--updates-json",
    required=True,
    help='JSON object of field name/ID -> value pairs (e.g. \'{"Status": "Active"}\').',
)
@output_options
@click.pass_obj
def list_entry_set_fields(
    ctx: CLIContext,
    list_selector: str,
    entry_id: int,
    *,
    updates_json: str,
) -> None:
    """
    Set multiple field values on a list entry at once.

    Field names are resolved case-insensitively. Field IDs can also be used.
    All field names are validated before any updates are applied.

    Examples:

    - `xaffinity list entry set-fields "Portfolio" 123 --updates-json '{"Status": "Active"}'`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        from ..field_utils import FieldResolver

        parsed = parse_json_value(updates_json, label="updates-json")
        if not isinstance(parsed, dict):
            raise CLIError(
                "--updates-json must be a JSON object.",
                exit_code=2,
                error_type="usage_error",
            )

        if not parsed:
            raise CLIError(
                "--updates-json cannot be empty.",
                exit_code=2,
                error_type="usage_error",
            )

        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        resolved = dict(resolved_list.resolved)

        # Fetch field metadata
        field_metadata = client.lists.get_fields(resolved_list.list.id)
        resolver = FieldResolver(field_metadata)

        # Validate all field names - this raises on any invalid names
        resolved_updates, _ = resolver.resolve_all_field_names_or_ids(parsed, context="field")

        # Convert string field IDs to typed FieldId/EnrichedFieldId
        typed_updates: dict[AnyFieldId, Any] = {}
        for fid_str, val in resolved_updates.items():
            try:
                typed_updates[FieldId(fid_str)] = val
            except ValueError:
                typed_updates[EnrichedFieldId(fid_str)] = val

        # Use batch update with resolved field IDs
        entries = client.lists.entries(resolved_list.list.id)
        result = entries.batch_update_fields(ListEntryId(entry_id), typed_updates)
        payload = serialize_model_for_cli(result)

        resolved["fieldsUpdated"] = len(resolved_updates)

        return CommandOutput(
            data={"fieldUpdates": payload},
            resolved=resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry set-fields", fn=fn)


@list_entry_group.command(name="unset-field", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@click.option("-f", "--field", "field_name", help="Field name (e.g. 'Status').")
@click.option("--field-id", help="Field ID (e.g. 'field-260415').")
@click.option("--value", help="Specific value to unset (for multi-value fields).")
@click.option("--all-values", "unset_all", is_flag=True, help="Unset all values for field.")
@output_options
@click.pass_obj
def list_entry_unset_field(
    ctx: CLIContext,
    list_selector: str,
    entry_id: int,
    *,
    field_name: str | None,
    field_id: str | None,
    value: str | None,
    unset_all: bool,
) -> None:
    """
    Unset a field value from a list entry.

    For multi-value fields, use --value to remove a specific value or
    --all-values to remove all values.

    Examples:

    - `xaffinity list entry unset-field "Portfolio" 123 --field Status`
    - `xaffinity list entry unset-field "Portfolio" 123 --field Tags --value "Priority"`
    - `xaffinity list entry unset-field "Portfolio" 123 --field Tags --all-values`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        from ..field_utils import (
            FieldResolver,
            find_field_values_for_field,
            format_value_for_comparison,
            validate_field_option_mutual_exclusion,
        )

        validate_field_option_mutual_exclusion(field=field_name, field_id=field_id)

        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        resolved = dict(resolved_list.resolved)

        # Fetch field metadata
        field_metadata = client.lists.get_fields(resolved_list.list.id)
        resolver = FieldResolver(field_metadata)

        target_field_id = (
            field_id
            if field_id
            else resolver.resolve_field_name_or_id(field_name or "", context="field")
        )
        resolved["fieldId"] = target_field_id
        resolved["fieldName"] = resolver.get_field_name(target_field_id)

        # Get existing field values
        existing_values = client.field_values.list(list_entry_id=ListEntryId(entry_id))
        existing_for_field = find_field_values_for_field(
            field_values=[serialize_model_for_cli(v) for v in existing_values],
            field_id=target_field_id,
        )

        if not existing_for_field:
            # Idempotent - success with warning
            field_label = resolved["fieldName"] or target_field_id
            warnings.append(f"Field '{field_label}' has no values on this list entry.")
            return CommandOutput(
                data={"deleted": 0},
                resolved=resolved,
                api_called=True,
            )

        # Determine which values to delete
        to_delete: list[dict[str, Any]] = []

        if len(existing_for_field) == 1:
            # Single value: delete it (no flags needed)
            to_delete = existing_for_field
        elif unset_all:
            # Multi-value with --all-values: delete all
            to_delete = existing_for_field
        elif value is not None:
            # Multi-value with --value: find matching value
            value_str = value.strip()
            for fv in existing_for_field:
                fv_value = fv.get("value")
                if format_value_for_comparison(fv_value) == value_str:
                    to_delete.append(fv)
                    break
            if not to_delete:
                field_label2 = resolved["fieldName"] or target_field_id
                raise CLIError(
                    f"Value '{value}' not found for field '{field_label2}'.",
                    exit_code=2,
                    error_type="not_found",
                )
        else:
            # Multi-value without --value or --all-values: error
            raise CLIError(
                f"Field has {len(existing_for_field)} values. "
                "Use --value to unset a specific value, or --all-values to unset all.",
                exit_code=2,
                error_type="usage_error",
            )

        # Delete the field values
        deleted_count = 0
        for fv in to_delete:
            fv_id = fv.get("id")
            if fv_id:
                client.field_values.delete(fv_id)
                deleted_count += 1

        return CommandOutput(
            data={"deleted": deleted_count},
            resolved=resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry unset-field", fn=fn)
